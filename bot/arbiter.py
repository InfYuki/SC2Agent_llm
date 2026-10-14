"""Small command gate for the units explicitly owned by custom combat code."""


class OrderArbiter:
    def __init__(self):
        self.owners = {}
        self.issued = set()
        self.conflicts = 0

    def begin_step(self, owners):
        self.owners = dict(owners)
        self.issued.clear()

    def allow(self, tag, owner):
        if self.owners.get(tag) != owner or tag in self.issued:
            self.conflicts += 1
            return False
        self.issued.add(tag)
        return True
