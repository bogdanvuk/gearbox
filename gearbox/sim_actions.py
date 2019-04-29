from PySide2.QtCore import Qt
from pygears.conf import Inject, inject
from .actions import Interactive, shortcut
from .main_window import register_prefix

register_prefix(None, (Qt.Key_Space, Qt.Key_S), 'simulator')


@inject
def step_simulator(sim_bridge=Inject('gearbox/sim_bridge')):
    sim_bridge.breakpoint(lambda: (True, False))
    if not sim_bridge.running:
        sim_bridge.cont()


@inject
def cont_simulator(
        timekeep=Inject('gearbox/timekeep')):
    timekeep.timestep = 0xffffffff


@inject
def time_search(
        time=Interactive('Time: '), timekeep=Inject('gearbox/timekeep')):

    try:
        time = int(time)
    except TypeError:
        return

    timekeep.timestep = time


shortcut(None, (Qt.Key_Space, Qt.Key_S, Qt.Key_S))(step_simulator)
shortcut(None, (Qt.Key_Space, Qt.Key_S, Qt.Key_C))(cont_simulator)
shortcut(None, (Qt.Key_Space, Qt.Key_S, Qt.Key_Colon))(time_search)
