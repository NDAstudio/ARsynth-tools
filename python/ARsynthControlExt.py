"""Extension class for the ARsynth_control component.

All of the component's behaviour lives here. The callback DATs are one-liners
that call into this class, so the logic is in one file you can read top to
bottom, and so the component can be driven from other scripts:

    ctl = op('/project1/ARsynth_control')
    ctl.Login()
    ctl.SetScene('Opening')
"""

import tempfile
import threading
import urllib.request


class ARsynthControl:

    def __init__(self, ownerComp):
        self.ownerComp = ownerComp
        self.api = mod(ownerComp.op('arsynth_api'))
        # Tokens live in memory only. Putting them in ownerComp.store() would
        # write them into the saved .toe/.tox file.
        self.session = None

    # -- helpers -----------------------------------------------------------

    @property
    def _shows(self):
        return self.ownerComp.op('shows')

    @property
    def _scenes(self):
        return self.ownerComp.op('scenes')

    def _client(self):
        par = self.ownerComp.par
        return self.api.ArsynthClient(par.Supabaseurl.eval(), par.Anonkey.eval())

    def _status(self, message):
        self.ownerComp.par.Status = message
        print(f'[ARsynth] {message}')

    def _valid_session(self):
        """Return a usable session, refreshing the token if it has expired."""
        if self.session is None:
            return None
        if not self.session.is_expired:
            return self.session
        try:
            self.session = self._client().refresh(self.session)
        except Exception as exc:
            self._status(f'Token refresh failed: {exc}')
            self.session = None
        return self.session

    @staticmethod
    def _fill(dat, rows):
        dat.clear()
        if not rows:
            return
        headers = list(rows[0].keys())
        dat.appendRow(headers)
        for row in rows:
            dat.appendRow([str(row.get(h, '')) for h in headers])

    @staticmethod
    def _menu(par, rows):
        """Fill a menu from API rows.

        Menu *names* are row numbers, not titles. TouchDesigner will not accept
        spaces, colons or '#' in a menu name, and scene titles routinely have
        all three — assigning such a name silently falls back to the first
        entry. The title goes in menuLabels, which has no such restriction.
        """
        par.menuNames = [str(i) for i in range(len(rows))]
        par.menuLabels = [str(row.get('title', '')) for row in rows]

    def _show_row(self):
        """Row in the shows DAT for the selected show, or None."""
        row = self.ownerComp.par.Show.menuIndex + 1
        return row if 0 < row < self._shows.numRows else None

    def _scene_row(self):
        """Row in the scenes DAT for the selected scene, or None."""
        row = self.ownerComp.par.Scene.menuIndex + 1
        return row if 0 < row < self._scenes.numRows else None

    def _scene_title(self):
        row = self._scene_row()
        return str(self._scenes[row, 'title']) if row else ''

    # -- connection --------------------------------------------------------

    def Login(self):
        par = self.ownerComp.par
        if not par.Email.eval() or not par.Password.eval():
            self._status('Fill in Email and Password first')
            return
        try:
            self.session = self._client().login(par.Email.eval(), par.Password.eval())
        except self.api.ArsynthApiError as exc:
            self._status(f'Login failed: {exc}')
            return
        self._status(f'Logged in as {self.session.user_email}')
        self.Refresh()

    def Logout(self):
        self.session = None
        self._status('Logged out')

    def Refresh(self):
        """Pull shows and scenes from Supabase into the tables and menus."""
        session = self._valid_session()
        if session is None:
            self._status('Not logged in')
            return
        client = self._client()
        try:
            shows = client.list_shows(session)
            scenes = client.list_scenes(session)
        except self.api.ArsynthApiError as exc:
            self._status(f'Refresh failed: {exc}')
            return

        self._fill(self._shows, shows)
        self._fill(self._scenes, scenes)
        self._menu(self.ownerComp.par.Show, shows)
        self._menu(self.ownerComp.par.Scene, scenes)
        self._status(f'{len(shows)} shows, {len(scenes)} scenes')
        self.ReadActiveScene()
        self.FetchQR()

    def Reset(self):
        self.Logout()
        for dat in (self._shows, self._scenes):
            dat.clear()
        for par in (self.ownerComp.par.Show, self.ownerComp.par.Scene):
            par.menuNames = []
            par.menuLabels = []
        self._publish_index(-1, '')
        self._status('Reset')

    # -- scene state -------------------------------------------------------

    def _publish_index(self, index, title):
        """Publish the active scene number for the rest of the network.

        Two places, because TouchDesigner networks reference things two ways:
        a parameter for expressions (op('ARsynth_control').par.Sceneindex) and a
        CHOP channel for anything that wants it as a signal.

        Nothing here guards against loops. It does not need to: every handler
        checks whether the value actually changed before writing, so a callback
        firing on a value it just published is a no-op.
        """
        if int(self.ownerComp.par.Sceneindex.eval()) != index:
            self.ownerComp.par.Sceneindex = index
        self.ownerComp.par.Activescene = title
        chop = self.ownerComp.op('scene_index')
        chop.par.name0 = 'scene'
        chop.par.value0 = index

    def OnSceneIndex(self):
        """Scene number was set from outside — make that scene live.

        This is the write side of Sceneindex: set it from any expression, CHOP
        export, MIDI mapping or script and the AR scene follows.
        """
        index = int(self.ownerComp.par.Sceneindex.eval())
        if not 0 <= index < self._scenes.numRows - 1:
            return
        self.ownerComp.par.Scene.menuIndex = index
        # Do the push here rather than leaving it to the Scene parameter's own
        # callback. TouchDesigner runs parameter callbacks a frame later, so
        # chaining them makes the outcome depend on frame order — and if two
        # writes land in the same frame, the intermediate one is never seen.
        self.PushActiveScene()

    def ReadActiveScene(self):
        """Mirror the selected show's active scene into the menu and scene_index.

        Read-only: this reflects what the server says, it never pushes back.
        Someone switching the scene from the web dashboard shows up here on the
        next refresh.
        """
        show = self._show_row()
        if show is None:
            return
        scene_id = str(self._shows[show, 'active_scene'])
        for r in range(1, self._scenes.numRows):
            if str(self._scenes[r, 'id']) == scene_id:
                if r - 1 != self.ownerComp.par.Scene.menuIndex:
                    self.ownerComp.par.Scene.menuIndex = r - 1
                self._publish_index(r - 1, str(self._scenes[r, 'title']))
                return
        self._publish_index(-1, '')

    def SetScene(self, title):
        """Make the scene with this title the active one, by title."""
        for i, label in enumerate(self.ownerComp.par.Scene.menuLabels):
            if label == title:
                self.ownerComp.par.Sceneindex = i
                return
        self._status(f'No scene called {title}')

    def PushActiveScene(self):
        """Send the selected scene to ARSynth so viewers switch to it.

        Does nothing if that scene is already the show's active one, which both
        saves a request and is what stops Scene and Sceneindex writing to each
        other in circles.
        """
        session = self._valid_session()
        if session is None:
            self._status('Not logged in')
            return

        show = self._show_row()
        scene = self._scene_row()
        if show is None or scene is None:
            return

        scene_id = str(self._scenes[scene, 'id'])
        title = str(self._scenes[scene, 'title'])
        if str(self._shows[show, 'active_scene']) == scene_id:
            self._publish_index(scene - 1, title)
            return

        try:
            self._client().set_active_scene(
                session, str(self._shows[show, 'id']), scene_id
            )
        except self.api.ArsynthApiError as exc:
            self._status(f'Switch failed: {exc}')
            return

        self._shows[show, 'active_scene'] = scene_id
        self._publish_index(scene - 1, title)
        self._status(f'Live: {title}')

    # -- show selection ----------------------------------------------------

    def OnShowChange(self):
        self.ReadActiveScene()
        self.FetchQR()

    def Poll(self):
        """Called by the refresh timer. Cheap: shows only, no scene list."""
        if not self.ownerComp.par.Autorefresh.eval():
            return
        session = self._valid_session()
        if session is None:
            return
        try:
            shows = self._client().list_shows(session)
        except self.api.ArsynthApiError:
            return
        self._fill(self._shows, shows)
        self.ReadActiveScene()

    def FetchQR(self):
        """Download the show's QR code in a thread and point the TOP at it."""
        show = self._show_row()
        if show is None:
            return
        show_id = str(self._shows[show, 'id'])
        target = self.ownerComp.op('qr_path').path
        image = self.ownerComp.op('qr_code').path
        context = self.api.ssl_context()

        def worker():
            # Temp folder, not the project folder: the QR is derived data, it
            # would otherwise pile up next to the .toe and carry the show id in
            # its filename.
            path = f'{tempfile.gettempdir()}/arsynth_qr_{show_id[:8]}.png'
            url = ('https://api.qrserver.com/v1/create-qr-code/?size=400x400&data='
                   f'https://view.arsynth.cc/?show_id={show_id}')
            try:
                with urllib.request.urlopen(url, timeout=15, context=context) as response:
                    data = response.read()
                with open(path, 'wb') as f:
                    f.write(data)
            except Exception as exc:
                run("print('[ARsynth] QR fetch failed:', args[0])", str(exc), delayFrames=1)
                return
            run('op(args[0]).text = args[1]', target, path, delayFrames=1)
            # The path may be unchanged from last time, and then the TOP will not
            # reload on its own.
            run('op(args[0]).par.reloadpulse.pulse()', image, delayFrames=2)

        threading.Thread(target=worker, daemon=True).start()
