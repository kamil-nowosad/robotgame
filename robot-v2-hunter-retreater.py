import rg
import random

_game = None
_myPlayerId = None
_gameView = None

def sub2d(loc1, loc2):
	return (loc1[0] - loc2[0], loc1[1] - loc2[1])

def wdist2d(loc1, loc2):
	return (abs(loc1[0] - loc2[0]), abs(loc1[1] - loc2[1]))

def towardFilteredOrCurrent(current_loc, dest_loc, filter_out = ('invalid', 'spawn')):
	loc_dist = [{"location": loc, "distance": rg.wdist(loc, dest_loc)} for loc in rg.locs_around(current_loc, filter_out) + [current_loc]]
	loc_dist = sorted(loc_dist, key=lambda x: (x["distance"], max(wdist2d(x["location"], dest_loc))))
	return loc_dist[0]["location"]

def canGoTo(location):
	return rg.loc_types(location) == ['normal']

def enemyAtLoc(location):
	assert _game['robots'].has_key(location), "Expected robot at location %s, loc_types: %s" % (location, rg.loc_types(location))
	return _game['robots'][location].player_id != _myPlayerId

def simpleResolveCollision(robot, goToLoc):
	if enemyAtLoc(goToLoc):
		return ['attack', goToLoc]
	if random.randint(0, 1) == 0:
		return ['guard']
	else:
		return ['move', goToLoc]

def minWDistFromEnemyRobot(location):
	locationsDistances = map(lambda loc: {"location": loc, "distance": rg.wdist(location, loc)}, _gameView.locationsOfEnemyRobots)
	return min(locationsDistances, key=lambda ld: ld["distance"])["distance"]

def printBasicMove(currentLocation, basicMove):
	result = str(basicMove)
	if basicMove[0] == "move":
		result += " (" + str(sub2d(basicMove[1], currentLocation)) + ")"
	return result

class Params:
	HP_RETREAT_THRESHOLD = 10 

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
		self.enemies = map(lambda (loc, robot): {'location': loc, 'robot': robot, 'numAttacking': 0}, self.enemyRobots)

		self.targets = None

	def calculateTargets(self):
		self.targets = {}

		for (myLoc, myRobot) in self.myRobots:
			enemy = min(self.enemies, key=lambda r: (r['numAttacking'] / 50, rg.wdist(myLoc, r['location'])))
			self.targets[myRobot['location']] = enemy['robot']
			enemy['numAttacking'] += 1

class Walker:
	def __init__(self, me):
		self.me = me
	
	def goTowards(self, location):
		newLocOrCurrent = towardFilteredOrCurrent(self.me.location, location)

		if newLocOrCurrent != self.me.location:
			if canGoTo(newLocOrCurrent):
				return Move(['move', newLocOrCurrent], "Walker %s" % str(location))
			else:
				print "Being at %s cannot go to %s chasing robot at %s" % (self.me.location, newLocOrCurrent, robot.location)
				return Move(simpleResolveCollision(self.me, newLocOrCurrent), "Walker %s (collision)" % str(location))
		
		return Move(['guard'], "Walker %s" % str(location))

class Hunter:
	def __init__(self, me):
		self.me = me

	def hunt(self, robot):
		if rg.wdist(self.me.location, robot.location) <= 1:
			return Move(['attack', robot.location], "Hunter %s" % str(robot.location))
		
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
	
	if robot.hp <= Params.HP_RETREAT_THRESHOLD:
		retreater = Retreater(robot)
		moveOrNone = retreater.tryRetreat()
		if moveOrNone:
			return moveOrNone	
		
	hunter = Hunter(robot)
	return hunter.hunt(_gameView.targets[robot.location])

class Robot:
		def act(self, game):
			global _game
			global _myPlayerId
			global _gameView
			_game = game
			_myPlayerId = self.player_id

			_gameView = GameView(game)
			_gameView.calculateTargets()

			move = calculateMove(self)
			why = move.getWhy()
			basicMove = move.getBasicMove()

			print "Turn %s, robot at %s (%s HP) has calculated move: %s by %s" % (game['turn'], self.location, self.hp, printBasicMove(self.location, basicMove), why)
			return basicMove
