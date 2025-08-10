# Импортируем все модели для автоматического создания таблиц
from .users import User
from .directories import Directory, DirectoryTag
from .tasks import Task, TaskTag
from .invitations import Invitation
from .members import Member, MemberTag
from .activities import Activity, ActivityTag, ActivityEmbed
