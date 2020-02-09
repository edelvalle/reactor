from django.utils.log import ServerFormatter


class ServerFormatter(ServerFormatter):
    def format(self, record):
        msg = record.msg
        if record.name == 'reactor':
            msg = self.style.SUCCESS(msg)
        elif record.name == 'django.db.backends':
            msg = self.style.SQL_KEYWORD(msg)
        record.msg = msg
        return super().format(record)
