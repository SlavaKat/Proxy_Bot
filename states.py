from aiogram.fsm.state import State, StatesGroup

class SupportStates(StatesGroup):
    WAITING_MESSAGE = State()
    ADMIN_REPLY = State()
    ADMIN_MEDIA = State()