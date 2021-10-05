import os
from dotenv import load_dotenv

load_dotenv()


class Emojis:
    def __init__(self):
        self.staff = '<:staff:884878278295425024>'
        self.yes = '<:yes:893130476871643166>'
        self.no = '<:no:893130503782297630>'
        self.loading = '<a:Loading:893130260089032725>'


class Logs:
    def __init__(self):
        self.cmds: int = 890079834808680449
        self.cmd_errs: int = 890079865175420969
        self.event_errs: int = 890079898453024878
        self.add_remove: int = 893129025822785557


class Config:
    def __init__(self):
        self.emojis = Emojis()
        self.logs = Logs()
        self.prefixes = ['v!', 'V!']
        self.status = 'my dms'
        self.owners = [739440618107043901]
        self.client_secret = os.environ.get('CLIENT_SECRET')
