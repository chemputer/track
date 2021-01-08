class MatchData:
    pass


class PlayerInfo:
    def __init__(self):
        self.id = 0
        self.accountId = 0
        self.avatarId = 0
        self.vehicleId = 0
        self.nickname = ""
        self.isOwner = False
        self.maxHealth = 0
        self.isAlly = False
        self.shipParamsId = 0
        self.teamId = 0


class PlayerState:
    def __init__(self):
        self.id = 0
        self.avatarId = 0
        self.vehicleId = 0
        self.isAbuser = False
        self.isAlive = False
        self.health = 0
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.isVisible = None

    def setPosition(self, x, y, yaw):
        self.isVisible = x != -2500.0 and y != -2500.0
        if self.isVisible:
            self.x = x
            self.y = y
            self.yaw = yaw


