import rg
import random

_game = None
_myPlayerId = None
_gameView = None
_potentialMovesByOtherRobots = None

def sub2d(loc1, loc2):
	return (loc1[0] - loc2[0], loc1[1] - loc2[1])

def wdist2d(loc1, loc2):
	return (abs(loc1[0] - loc2[0]), abs(loc1[1] - loc2[1]))

def getEstimatedLocationsOfMorePrivilegedRobots(current_loc):
	if _potentialMovesByOtherRobots is None:
		return []
	morePrivilegedRobots = filter(lambda move: move["robot"]["location"] < current_loc, _potentialMovesByOtherRobots)
	robotsMoving = filter(lambda move: move["move"].getBasicMove()[0] == "move", morePrivilegedRobots)
	locations = map(lambda move: move["move"].getBasicMove()[1], robotsMoving)
	return locations

def towardFilteredOrCurrent(current_loc, dest_loc):
	filter_out = ['invalid']
	if not 'spawn' in rg.loc_types(current_loc):
		filter_out.append('spawn')

	currentPositionsOfOthers = _game['robots'].keys()
	estimatedFuturePositionsOfOthers = getEstimatedLocationsOfMorePrivilegedRobots(current_loc)
	forbiddenLocations = currentPositionsOfOthers + estimatedFuturePositionsOfOthers
		
	goableLocations = filter(lambda loc: filter(lambda l: l == loc, forbiddenLocations) == [], rg.locs_around(current_loc, filter_out))
	if goableLocations == []:
		return current_loc

	loc_dist = [{"location": loc, "distance": rg.wdist(loc, dest_loc)} for loc in goableLocations]
	loc_dist = sorted(loc_dist, key=lambda x: (x["distance"], max(wdist2d(x["location"], dest_loc))))
	# print loc_dist
	return loc_dist[0]["location"]

def enemyAtLoc(location):
	assert _game['robots'].has_key(location), "Expected robot at location %s, loc_types: %s" % (location, rg.loc_types(location))
	return _game['robots'][location].player_id != _myPlayerId

def minWDistFromEnemyRobot(location):
	locationsDistances = map(lambda loc: {"location": loc, "distance": rg.wdist(location, loc)}, _gameView.locationsOfEnemyRobots)
	return min(locationsDistances, key=lambda ld: ld["distance"])["distance"]

def printBasicMove(currentLocation, basicMove):
	result = str(basicMove)
	if basicMove[0] == "move":
		result += " (" + str(sub2d(basicMove[1], currentLocation)) + ")"
	return result

class Params:
	HP_RETREAT_THRESHOLD = -1

	RETR_RADIUS_ENEMY = 3
	RETR_ENEMY_COUNT_THRESHOLD = 2
	RETR_RADIUS_FRIENDLY = 3
	RETR_FRIENDLY_COUNT_THRESHOLD = 2 # "self" is counted in

class Move:
	def __init__(self, move, why):
		self.move = move
		self.why = why

	def getWhy(self):
		result = self.why
		if isinstance(self.move, Move):
			result += "[" + self.move.getWhy() + "]"	
		return result	

	def getBasicMove(self):
		if isinstance(self.move, Move):
			return self.move.getBasicMove()
		else:
			return self.move 

class GameView:
	def __init__(self, game):
		self.myRobots = filter(lambda (loc, robot): robot['player_id'] == _myPlayerId, _game['robots'].iteritems())
		self.enemyRobots = filter(lambda (loc, robot): robot.player_id != _myPlayerId, _game['robots'].iteritems())
		self.locationsOfEnemyRobots = map(lambda x: x[0], self.enemyRobots)
		self.locationsOfMyRobots = map(lambda x: x[0], self.myRobots)
		self.enemies = map(lambda (loc, robot): {'location': loc, 'robot': robot, 'numAttacking': 0}, self.enemyRobots)


		self.targets = None

	def calculateTargets(self):
		self.targets = {}

		for (myLoc, myRobot) in self.myRobots:
			enemy = min(self.enemies, key=lambda r: (r['numAttacking'] / 50, rg.wdist(myLoc, r['location'])))
			self.targets[myRobot['location']] = enemy['robot']
			enemy['numAttacking'] += 1
		#print self.targets

class Walker:
	def __init__(self, me):
		self.me = me
	
	def goTowards(self, location):
		newLocOrCurrent = towardFilteredOrCurrent(self.me.location, location)

		if newLocOrCurrent != self.me.location:
			return Move(['move', newLocOrCurrent], "Walker %s" % str(location))
		else:		
			return Move(['guard'], "Walker %s" % str(location))

class Hunter:
	def __init__(self, me):
		self.me = me

	def hunt(self, robot):
		if rg.wdist(self.me.location, robot.location) <= 1:
			return Move(['attack', robot.location], "Hunter %s" % str(robot.location))
		for enemyRobotLocation in _gameView.locationsOfEnemyRobots:
			if rg.wdist(self.me.location, enemyRobotLocation) <= 1:
				return Move(['attack', enemyRobotLocation], "Hunter [found other enemy] %s" % str(enemyRobotLocation))
		
		walker = Walker(self.me)
		return Move(walker.goTowards(robot.location), "Hunter %s [needed to walk]" % str(robot.location))

class Retreater:
	def __init__(self, me):
		self.me = me

	def tryRetreat(self):
		potentialLocations = rg.locs_around(self.me.location, filter_out = ("invalid", "spawn"))
		if not potentialLocations:
			return None
		locationsWithMinDistsFromEnemies = map(lambda loc: {"location": loc, "minDistance": minWDistFromEnemyRobot(loc)}, potentialLocations)
		sortedLocations = sorted(locationsWithMinDistsFromEnemies, key = lambda d: d['minDistance'])
		locationAwayFromEnemies = sortedLocations[-1]["location"]
		return Move(['move', locationAwayFromEnemies], "Retreater")

def calculateMove(robot):
	if 'spawn' in rg.loc_types(robot.location):
		walker = Walker(robot)
		return walker.goTowards(rg.CENTER_POINT)

	def numberOfRobotsInRadius(location, robots, radius):
		return len(filter(lambda robot: rg.wdist(robot, location) <= radius, robots))

	almostDead = robot.hp <= Params.HP_RETREAT_THRESHOLD 
	closeEnemies = numberOfRobotsInRadius(robot.location, _gameView.locationsOfEnemyRobots, Params.RETR_RADIUS_ENEMY)
	closeFriends = numberOfRobotsInRadius(robot.location, _gameView.locationsOfMyRobots, Params.RETR_RADIUS_FRIENDLY)
	surroundedByEnemies =	(closeEnemies >= Params.RETR_ENEMY_COUNT_THRESHOLD and closeFriends < Params.RETR_FRIENDLY_COUNT_THRESHOLD)
	shouldRetreat = almostDead or surroundedByEnemies

	if shouldRetreat:
		print "Will retreat, %s, %s" % (almostDead, surroundedByEnemies)
		retreater = Retreater(robot)
		moveOrNone = retreater.tryRetreat()
		if moveOrNone:
			return moveOrNone	
		
	hunter = Hunter(robot)
	return hunter.hunt(_gameView.targets[robot.location])

class InternalRobot:
	def __init__(self, location, hp):
		self.location = location
		self.hp = hp

def estimateMovesOfOtherRobots(me):
	myOtherRobots = map(lambda (loc, robot): robot, filter(lambda (loc, robot): loc != me.location, _gameView.myRobots))
	movesOfMyOtherRobots = map(lambda robot: {"robot": robot, "move": calculateMove(InternalRobot(robot["location"], robot["hp"]))}, myOtherRobots)
	return movesOfMyOtherRobots

class Robot:
		def act(self, game):
			global _game
			global _myPlayerId
			global _gameView
			global _potentialMovesByOtherRobots

			_game = game
			_myPlayerId = self.player_id

			_gameView = GameView(game)
			_gameView.calculateTargets()
			
			_potentialMovesByOtherRobots = estimateMovesOfOtherRobots(self)

			move = calculateMove(self)

			why = move.getWhy()
			basicMove = move.getBasicMove()

			print "Turn %s, robot at %s (%s HP) has calculated move: %s by %s" % (game['turn'], self.location, self.hp, printBasicMove(self.location, basicMove), why)
			return basicMove
