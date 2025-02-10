from rq.group import Group


class GroupExt(Group):
    """Subclass of rq Group that adds some convenience methods"""

    def is_finished(self):
        return all(j.is_finished for j in self.get_jobs())

    def is_failed(self):
        return any(j.is_failed for j in self.get_jobs())
