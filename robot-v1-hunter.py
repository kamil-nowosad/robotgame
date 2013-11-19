import rg
import random

_game = None
_myPlayerId = None

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

class Walker:
	def __init__(self, me):
		self.me = me
	
	def goTowards(self, location):
		newLocOrCurrent = towardFilteredOrCurrent(self.me.location, location)

		if newLocOrCurrent != self.me.location:
			if canGoTo(newLocOrCurrent):
				return ['move', newLocOrCurrent]
			else:
				print "Being at %s cannot go to %s chasing robot at %s" % (self.me.location, newLocOrCurrent, robot.location)
				return simpleResolveCollision(self.me, newLocOrCurrent)
		
		print "Is it possible at all? Guarding at %s, but wanting to go to %s" % (self.me.location, location)
		return ['guard']

class Hunter:
	def __init__(self, me):
		self.me = me

	def hunt(self, robot):
		if rg.wdist(self.me.location, robot.location) <= 1:
			return ['attack', robot.location]
		
		walker = Walker(self.me)
		return walker.goTowards(robot.location)

def assignTargets():
	targets = {}
	myRobots = filter(lambda (loc, robot): robot['player_id'] == _myPlayerId, _game['robots'].iteritems())
	enemyRobots = filter(lambda (loc, robot): robot.player_id != _myPlayerId, _game['robots'].iteritems())
	enemies = map(lambda (loc, robot): {'location': loc, 'robot': robot, 'numAttacking': 0}, enemyRobots)

	for (myLoc, myRobot) in myRobots:
		enemy = min(enemies, key=lambda r: (r['numAttacking'] / 50, rg.wdist(myLoc, r['location'])))
		targets[myRobot['location']] = enemy['robot']
		enemy['numAttacking'] += 1
		# print "DBG: %s" % enemies

	return targets

def calculateMove(robot):
	if 'spawn' in rg.loc_types(robot.location):
		walker = Walker(robot)
		return walker.goTowards(rg.CENTER_POINT)
		
	hunter = Hunter(robot)
	targets = assignTargets()
	return hunter.hunt(targets[robot.location])

class Robot:
		def act(self, game):
			global _game
			global _myPlayerId
			_game = game
			_myPlayerId = self.player_id
			move = calculateMove(self)
			print "Turn %s, robot at %s has calculated move: %s" % (game['turn'], self.location, move)
			return move
