# Refresh timer. Replaces polling in onFrameStart, which ran 60x a second
# only to compare two timestamps and return.


def onCycle(timerOp, segment, interrupt):
    timerOp.parent().ext.ARsynthControl.Poll()
    return
