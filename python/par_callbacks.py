# Routes parameter changes to the extension. The behaviour itself lives in
# ARsynthControlExt.py.

ACTIONS = {
    'Login':   lambda ext: ext.Login(),
    'Logout':  lambda ext: ext.Logout(),
    'Refresh': lambda ext: ext.Refresh(),
    'Reset':   lambda ext: ext.Reset(),
    'Show':    lambda ext: ext.OnShowChange(),
    'Scene':   lambda ext: ext.PushActiveScene(),
    'Sceneindex': lambda ext: ext.OnSceneIndex(),
}


def onPulse(par):
    action = ACTIONS.get(par.name)
    if action:
        action(par.owner.ext.ARsynthControl)


def onValueChange(par, prev):
    action = ACTIONS.get(par.name)
    if action:
        action(par.owner.ext.ARsynthControl)
