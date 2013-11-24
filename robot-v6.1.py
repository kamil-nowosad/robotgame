import rg
import random
import Queue
import sys
import copy

class Constants:
	MIN_HP_GIVEN_BY_ATTACKER = 8
	MAX_HP_GIVEN_BY_ATTACKER = 10

class Params:
	HP_RETREAT_THRESHOLD = Constants.MAX_HP_GIVEN_BY_ATTACKER

	RETR_RADIUS_ENEMY = 2
	RETR_ENEMY_COUNT_THRESHOLD = 2
	RETR_RADIUS_FRIENDLY = 2
	RETR_FRIENDLY_COUNT_THRESHOLD = 1
	MIN_HP_FOR_TCTC = 10

_game = None
_myPlayerId = None
_gameView = None
_movesByOtherRobots = None

def sub2d(loc1, loc2):
	return (loc1[0] - loc2[0], loc1[1] - loc2[1])

def wdist2d(loc1, loc2):
	return (abs(loc1[0] - loc2[0]), abs(loc1[1] - loc2[1]))

def minWDistFromEnemyRobot(location):
	locationsDistances = map(lambda loc: {"location": loc, "distance": rg.wdist(location, loc)}, _gameView.locationsOfEnemyRobots)
	return min(locationsDistances, key=lambda ld: ld["distance"])["distance"]

class Move:
	def __init__(self, move, why):
		if not isinstance(move, Move):
			if move[0] == "move":
				assert isinstance(move[1][0], int) and isinstance(move[1][1], int), "%s" % move
		
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
	#(initialGameMap, initialObjMap, initialFeatureToLoc) = (None, None, None)

	def __init__(self, game):
		self.myRobots = filter(lambda (loc, robot): robot['player_id'] == _myPlayerId, _game['robots'].iteritems())
		self.enemyRobots = filter(lambda (loc, robot): robot.player_id != _myPlayerId, _game['robots'].iteritems())
		self.locationsOfEnemyRobots = map(lambda x: x[0], self.enemyRobots)
		self.locationsOfMyRobots = map(lambda x: x[0], self.myRobots)
		self.enemies = map(lambda (loc, robot): {'location': loc, 'robot': robot, 'numAttacking': 0}, self.enemyRobots)

		self.gameMap = None
		self.objMap = None
		self.featureToLoc = None

		self.gameMapPerEntireTurn = None
		self.objMapPerEntireTurn = None
		self.featureToLocPerEntireTurn = None
	
		self.targets = None

	def calculateMap(self):
		#self.gameMapPerEntireTurn = copy.deepcopy(GameView.initialGameMap)
		#self.objMapPerEntireTurn = copy.deepcopy(GameView.initialObjMap)
		self.gameMapPerEntireTurn = {}
		self.objMapPerEntireTurn = {}
		self.featureToLocPerEntireTurn = {}

		for (enemyRobotLoc, enemyRobot) in self.enemyRobots:
			(x, y) = enemyRobotLoc
			self.gameMapPerEntireTurn.setdefault(x, {}).setdefault(y, []).append("enemy_robot")
			self.featureToLocPerEntireTurn.setdefault("enemy_robot", []).append((x, y))

			self.objMapPerEntireTurn.setdefault(x, {}).setdefault(y, {})["enemyRobot"] = enemyRobot

			for (dx, dy) in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
				if "enemy_can_attack" in self.gameMapPerEntireTurn.get(x + dx, {}).get(y + dy, []):
					self.gameMapPerEntireTurn.setdefault(x + dx, {}).setdefault(y + dy, []).append("2_enemies_can_attack")
					self.featureToLocPerEntireTurn.setdefault("2_enemies_can_attack", []).append((x + dx, y + dy))
				else:
					self.gameMapPerEntireTurn.setdefault(x + dx, {}).setdefault(y + dy, []).append("enemy_can_attack")
					self.featureToLocPerEntireTurn.setdefault("enemy_can_attack", []).append((x + dx, y + dy))

	def updateFriendlyMoves(self):
		#self.gameMap = copy.deepcopy(self.gameMapPerEntireTurn)
		#self.objMap = copy.deepcopy(self.objMapPerEntireTurn)
		self.gameMap = {}
		self.objMap = {}
		self.featureToLoc = {}

		for moveAndRobot in _movesByOtherRobots:
			(move, robot) = (moveAndRobot["move"], moveAndRobot["robot"])
			basicMove = move.getBasicMove()

			if basicMove[0] == "move":
				(x, y) = basicMove[1]
			else:
				(x, y) = robot.location

			self.gameMap.setdefault(x, {}).setdefault(y, []).append("friendly_robot")
			self.featureToLoc.setdefault("friendly_robot", []).append((x, y))

			if basicMove[0] == "attack":
				(x, y) = basicMove[1]
				self.gameMap.setdefault(x, {}).setdefault(y, []).append("attacked")
				self.featureToLoc.setdefault("attacked", []).append((x, y))

		#locsOfMovedRobots = map(lambda m: m["robot"]["location"], _movesByOtherRobots)
		#for loc in self.locationsOfMyRobots:
		#	if loc in locsOfMovedRobots:
		#		continue
		#	else:
		#		(x, y) = loc
		#		self.gameMap.setdefault(x, {}).setdefault(y, []).append("friendly_robot")
		#		self.featureToLoc.setdefault("friendly_robot", []).append((x, y))
				

	def getGameMap(self, x, y):
		return self.gameMap.get(x, {}).get(y, []) + self.gameMapPerEntireTurn.get(x, {}).get(y, []) + GameView.initialGameMap.get(x, {}).get(y, [])
	
	def getObjMap(self, x, y):
		l = [k for k in self.objMap.get(x, {}).get(y, {}).iteritems()] + [k for k in self.objMapPerEntireTurn.get(x, {}).get(y, {}).iteritems()] + [k for k in GameView.initialObjMap.get(x, {}).get(y, {}).iteritems()]
		d = dict(l)
		return d

	@staticmethod
	def prepareInitialMaps():
		gameMap = {}
		objMap = {}
		featureMap = {}
		
		possibleFeatures = [
			"invalid",
			"obstacle",
			"spawn",
			"normal",
			"friendly_robot",
			"enemy_robot",
			"attacked",
			"enemy_can_attack",
			"2_enemies_can_attack"
		]

		for feature in possibleFeatures:
			featureMap[feature] = []
	
		for x in range(0, 20):
			gameMap[x] = {}
			objMap[x] = {}
			for y in range(0, 20):
				gameMap[x][y] = []
				for k in rg.loc_types((x, y)):
					gameMap[x][y].append(k)
					featureMap[k].append((x, y))
				objMap[x][y] = {} #{"enemyRobot": None}
		for k in range(20):
			featureMap["invalid"].append((k, -1))
			featureMap["invalid"].append((k, 20))
			featureMap["invalid"].append((-1, k))
			featureMap["invalid"].append((20, k))

		basicForbiddenObstacleInvalid = set(featureMap["invalid"] + featureMap["obstacle"])
		basicForbiddenObstacleInvalidSpawn = copy.deepcopy(basicForbiddenObstacleInvalid).union(set(featureMap["spawn"]))
		#print "BasicForbiddenObstacleInvalid: %s" %	basicForbiddenObstacleInvalid
		return (gameMap, objMap, featureMap, basicForbiddenObstacleInvalid, basicForbiddenObstacleInvalidSpawn)

(GameView.initialGameMap, GameView.initialObjMap, GameView.initialFeatureToLoc, GameView.basicForbiddenObstacleInvalid, GameView.basicForbiddenObstacleInvalidSpawn) = GameView.prepareInitialMaps()

class PathComputer:
	def __init__(self, fieldsToAvoid = []):
		self.filterOut = self.__calculateFilter(fieldsToAvoid)
		
		self.basicForbidden = None	
		self.forbiddenLocations = None
		self.forbiddenLocationsSet = None

		self.fieldsToAvoid = fieldsToAvoid

	def calcDistanceResultCheap(self, current_loc, dest_loc):
		#print "C %s, %s" % (str(dest_loc), self.fieldsToAvoid)
		wdist = rg.wdist(current_loc, dest_loc) 
		if wdist <= 5:
			return self.calcDistanceResult(current_loc, dest_loc)
		else:
			loc = self.locationTowards(current_loc, dest_loc)
			if loc:	
				return {"distance": wdist + 10, "prev": loc}
			else:
				return {"distance": 9999, "prev": None}

	def calcDistanceResult(self, current_loc, dest_loc):
		dmap = self.__bfs(dest_loc, current_loc)
		dresult = dmap.get(current_loc[0], {}).get(current_loc[1], {"prev": None, "distance": 9999})
		return dresult

	def getDistance(self, current_loc, dest_loc):
		return self.calcDistanceResult(current_loc, dest_loc)["distance"]

	def goTo(self, current_loc, dest_loc):
		dr = self.calcDistanceResult(current_loc, dest_loc)
		return dr["prev"]

	def locationTowards(self, source, target):
		locs = self.locationsAround(source)
		if locs:
			location = min((rg.wdist(loc, target), loc) for loc in locs)[1]
			#print "loc: %s, filter: %s, forbidden: %s" % (location, self.filterOut, self.forbiddenLocations)
			return location
		else:
			return None
			
	def locationsAround(self, (x, y)):
		self.__calculateForbiddenLocations()

		result = []
		for (dx, dy) in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
			(newx, newy) = (x + dx, y + dy)
			if (newx, newy) in self.forbiddenLocationsSet	or (newx, newy) in self.basicForbidden:
				#print "loc: %s, %s, %s, %s, %s" % (str((newx, newy)), (newx, newy) in self.forbiddenLocationsSet, (newx, newy) in self.basicForbidden, _gameView.getGameMap(x, y), self.fieldsToAvoid)
				continue
			result.append((newx, newy))
		return result
	
	def __calculateFilter(self, fieldsToAvoid):
		f = []
		for field in fieldsToAvoid:
			if field != "spawn":
				f.append(field)
		f.append("friendly_robot")
		f.append("enemy_robot")

		return f

	def __calculateForbiddenLocations(self):
		if self.forbiddenLocations:
			return
		
		if "spawn" in self.fieldsToAvoid:
			self.basicForbidden = _gameView.basicForbiddenObstacleInvalidSpawn
		else:
			self.basicForbidden = _gameView.basicForbiddenObstacleInvalid
			
		forbidden = []

		for feature in self.filterOut:
			#if feature == "friendly_robot":
				#print "friendly robot: %s" % (_gameView.featureToLoc.get(feature, []) + _gameView.featureToLocPerEntireTurn.get(feature, []))
			#if feature == "enemy_robot":
				#print "enemy robot: %s" % (_gameView.featureToLoc.get(feature, []) + _gameView.featureToLocPerEntireTurn.get(feature, []))
			forbidden += _gameView.featureToLoc.get(feature, []) + _gameView.featureToLocPerEntireTurn.get(feature, [])
		
		self.forbiddenLocations = forbidden
		self.forbiddenLocationsSet = set(forbidden)

	def __bfs(self, source, target):
		#print "D %s, %s" % (str(source), self.fieldsToAvoid)
		dmap = {} #copy.deepcopy(PathComputer.initialDmap)

		dmap.setdefault(source[0], {})[source[1]] = {"distance": 0, "prev": None}
		fifo = Queue.Queue()
		fifo.put(source)
			
		targetFound = False	
		while not fifo.empty() and not targetFound:
			(x, y) = fifo.get()

			dist = dmap[x][y]["distance"]
			for (newx, newy) in self.locationsAround((x, y)):
				dest = dmap.get(newx, {}).get(newy, None)
				if dest == None and (newx, newy) != source:
					dmap.setdefault(newx, {})[newy] = {"prev": (x, y), "distance": dist + 1}
					if (newx, newy) == target:
						targetFound = True
						break
					fifo.put((newx, newy))

		return dmap

	@staticmethod
	def calculateInitialObjects():	
		dmap = {}
		for x in range(20):
			dmap[x] = {}
		return dmap

PathComputer.initialDmap = PathComputer.calculateInitialObjects()

class Walker:
	def __init__(self, me, pathComputer):
		self.me = me
		self.pathComputer = pathComputer

	def tryGoTowards(self, location):
		newLocOrCurrent = self.pathComputer.goTo(self.me.location, location)

		if newLocOrCurrent:
			return Move(['move', newLocOrCurrent], "Walker %s" % str(location))
		else:
			return None

class Hunter:
	def __init__(self, me):
		self.me = me

	def tryToChaseARobot(self, robots):
		pc = PathComputer(["spawn", "2_enemies_can_attack"])
		potentialTargets = []
		for (location, robot) in robots:
			potentialTargets.append({"loc": location, "robot": robot, "dresult": pc.calcDistanceResultCheap(self.me.location, location)})
		
		potentialTargets = filter(lambda target: target["dresult"]["prev"] is not None, potentialTargets)
		if not potentialTargets:
			return None
		target = min(potentialTargets, key = lambda target: target["dresult"]["distance"])
		return Move(['move', target["dresult"]["prev"]], "Hunter(hunting a single robot, %s)" % (str(target["loc"])))

	def tryAttackRobotAround(self):
		for (x, y) in rg.locs_around(self.me.location):
			if "enemy_robot" in _gameView.getGameMap(x, y):
				friendsAttacking = _gameView.getGameMap(x, y).count("attacked")
				enemyRobot = _gameView.getObjMap(x, y)["enemyRobot"]
				if friendsAttacking * Constants.MIN_HP_GIVEN_BY_ATTACKER < enemyRobot["hp"]:
					return Move(['attack', (x, y)], "Hunter [tryAttackRobotAround]")
				else:
					print "Not attacking, already attacked by friends: %s, HP: %s" % (_gameView.getGameMap(x, y), enemyRobot["hp"])
		return None
	
	def tryHunt(self):
		moveOrNone = self.tryAttackRobotAround()
		if moveOrNone:
			return moveOrNone	

		moveOrNone = self.tryToChaseARobot(filter(lambda (loc, _): rg.wdist(loc, self.me.location) > 1, _gameView.enemyRobots))
		if moveOrNone:
			return moveOrNone

		moveOrNone = self.tryToChaseARobot(_gameView.myRobots)
		return moveOrNone

class Retreater:
	def __init__(self, me):
		self.me = me

		self.almostDead = self.me.hp <= Params.HP_RETREAT_THRESHOLD 
		self.numFriendsNearby = self.numberOfRobotsInRadius(_gameView.myRobots, 2) - 1
		
		self.enemiesAdjacent = self.robotsInRadius(_gameView.enemyRobots, 1)
		self.numEnemiesAdjacent = len(self.enemiesAdjacent)

		self.enemiesNearby = self.robotsInRadius(_gameView.enemyRobots, 2)
		self.numEnemiesNearby = len(self.enemiesNearby)

	def trySafelyGoingToBestPlace(self): # TODO to center? raczej do najblizszych swoich
		if rg.wdist(self.me.location, rg.CENTER_POINT) <= 2:
			return None
		pc = PathComputer(["spawn", "enemy_can_attack"])
		return pc.goTo(self.me.location, rg.CENTER_POINT)
	
	def trySafelyEscaping(self):
		pc = PathComputer(["spawn", "enemy_can_attack"])
		locAround = pc.locationsAround(self.me.location)
		if locAround:
			return locAround[0]
		return None

	def tryLessSafelyEscaping(self):
		pc = PathComputer(["spawn"])
		locAround = pc.locationsAround(self.me.location)
		if locAround:
			return locAround[0]
		return None

	def tryRetreat(self):
		step = self.trySafelyGoingToBestPlace()
		if step:
			return Move(["move", step], "Retreater (safelyToCenter)")
		
		step = self.trySafelyEscaping()
		if step:
			return Move(["move", step], "Retreater (trySafelyEscaping)")
		
		step = self.tryLessSafelyEscaping()
		if step:
			return Move(["move", step], "Retreater (tryLessSafelyEscaping)")

		return None

	def robotsInRadius(self, robots, radius):
		return filter(lambda (loc, robot): rg.wdist(loc, self.me.location) <= radius, robots)

	def numberOfRobotsInRadius(self, robots, radius):
		return len(self.robotsInRadius(robots, radius))
	
	def shouldRetreat(self):
		# jestes w zacieciu - uciekaj	
	
		# ..2..
		# .212.
		# .1X1.	
		# .212.
		# ..2..

		# nearby = 2
		# adjactent = 1

		shouldRetreat = \
			(self.almostDead and self.numFriendsNearby <= 1 and self.numEnemiesAdjacent >= 1) or \
			(self.numEnemiesAdjacent >= 2 and self.numFriendsNearby <= 1) or \
			self.numEnemiesAdjacent >= 2 # TODO bylo >= 3  -> robociki z mala liczba HP bywa, ze walcza bez sensu

		return shouldRetreat
	
	def isAboutToBeKilled(self):
		if self.me.hp > Constants.MAX_HP_GIVEN_BY_ATTACKER:
			return [False]
		enemiesAround = self.robotsInRadius(_gameView.enemyRobots, 1)
		numEnemiesAround = len(enemiesAround)
		if numEnemiesAround >= 2:
			return [True, 1, numEnemiesAround]
		if numEnemiesAround == 0:
			return [False]
		if enemiesAround[0][1]["hp"] <= Constants.MIN_HP_GIVEN_BY_ATTACKER:
			return [False]
		return [True, 2, enemiesAround[0][1]["hp"]]

	def tryCatchTheChaser(self):
		if self.me.hp > Params.MIN_HP_FOR_TCTC: # TODO tctc moze byc bardzo dobre. warto dobrze stroic ;)
			return None	
		if self.numEnemiesNearby == 1 and self.numEnemiesAdjacent == 0:
			enemyLocation = self.enemiesNearby[0][0]
			# someone already attacking
			for loc in _gameView.locationsOfMyRobots:
				if rg.wdist(loc, enemyLocation) == 1:
					return None

			distances = filter(lambda (dist, _): dist == 1, [(rg.wdist(loc, enemyLocation), loc) for loc in rg.locs_around(self.me.location, filter_out = ['invalid'])])
			if len(distances) == 1:
				bestMove = distances[0][1]
			elif len(distances) == 2:
				bestMove = distances[_game["turn"] % 2][1]
			else:
				print "ERROR, distances: %s, enemyLocation: %s, myLocation: %s" % (distances, enemyLocation, self.me)
				return None
			return Move(["attack", bestMove], "Retreater(tctc), %s" % len(distances))
		return None
	
	def tryRetreatIfApplicable(self):
		shouldRetreatResult = self.shouldRetreat()
		if shouldRetreatResult:
			tryRetreatResult = self.tryRetreat()
			if tryRetreatResult:
				return tryRetreatResult
			isAboutToBeKilledResult = self.isAboutToBeKilled()
			if isAboutToBeKilledResult[0]:
				return Move(["suicide"], "Retreater(no option to escape, suicide, %s)!" % isAboutToBeKilledResult[1:])
			print "%s should retreat, but could not" % (str(self.me.location))
		
		catchTheChaserOrNone = self.tryCatchTheChaser()
		if catchTheChaserOrNone:
			return catchTheChaserOrNone
		return None		

class SpawnEscaper:
	def __init__(self, me):
		self.me = me

	def tryEscapeSpawnIfApplicable(self):
		if not ('spawn' in rg.loc_types(self.me.location)):
			return None # N/A
		#print "escaping spawn"
		walker = Walker(self.me, PathComputer(["spawn"]))
		moveOrNone = walker.tryGoTowards(rg.CENTER_POINT)
		if moveOrNone:	
			return Move(moveOrNone, "SpawnEscaper 1")

		walker = Walker(self.me, PathComputer([]))
		moveOrNone = walker.tryGoTowards(rg.CENTER_POINT)
		if moveOrNone:	
			#print "gameMap: %s" % _gameView.getGameMap(moveOrNone.getBasicMove()[1][0], moveOrNone.getBasicMove()[1][1])
			return Move(moveOrNone, "SpawnEscaper 2")

		pc = PathComputer(["spawn"])
		locAround = pc.locationsAround(self.me.location)
		if locAround:
			#print "gameMap: %s" % _gameView.getGameMap(locAround[0][0], locAround[0][1])
			return Move(["move", locAround[0]], "SpawnEscaper 3")
		
		pc = PathComputer([])
		locAround = pc.locationsAround(self.me.location)
		if locAround:
			#print "gameMap: %s" % _gameView.getGameMap(locAround[0][0], locAround[0][1])
			return Move(["move", locAround[0]], "SpawnEscaper 4")

		#print "could not escape spawn"
		return None		

class Robot:
	@staticmethod
	def printBasicMove(currentLocation, basicMove):
		result = str(basicMove)
		if basicMove[0] == "move":
			result += " (" + str(sub2d(basicMove[1], currentLocation)) + ")"
		return result

	def estimateMovesOfOtherRobots(self):
		class InternalRobot:
			def __init__(self, location, hp):
				self.location = location
				self.hp = hp

		myRobotsSortedDescByPrivilege = sorted(_gameView.myRobots, key = lambda (loc, _): loc)

		global _movesByOtherRobots
		_movesByOtherRobots = []

		for (loc, robot) in myRobotsSortedDescByPrivilege:
			if loc == self.location:
				break
			if rg.wdist(loc, self.location) <= 3:	
				move = Robot.calculateMove(InternalRobot(robot["location"], robot["hp"]))
				#print "calculating move of robot at %s, move: %s" % (str(loc), move.getBasicMove())
				_movesByOtherRobots.append({"robot": robot, "move": move})

	def act(self, game):
		global _game
		global _myPlayerId
		global _gameView

		_game = game
		_myPlayerId = self.player_id
		_gameView = GameView(game)
		_gameView.calculateMap()

		self.estimateMovesOfOtherRobots() # TODO ograniczyc do najblizszego otoczenia

		move = Robot.calculateMove(self)

		why = move.getWhy()
		basicMove = move.getBasicMove()

		print "Turn %s, robot at %s (%s HP) has calculated move: %s by %s" % (game['turn'], self.location, self.hp, self.printBasicMove(self.location, basicMove), why)
		return basicMove

	@staticmethod
	def calculateMove(robot):
		_gameView.updateFriendlyMoves()

		spawnEscaper = SpawnEscaper(robot)
		moveOrNone = spawnEscaper.tryEscapeSpawnIfApplicable()
		if moveOrNone:	
			return moveOrNone

		retreater = Retreater(robot)
		moveOrNone = retreater.tryRetreatIfApplicable()
		if moveOrNone:
			return moveOrNone
	
		hunter = Hunter(robot)
		moveOrNone = hunter.tryHunt()
		if moveOrNone:
			return moveOrNone

		return Move(["guard"], "Nothing to do :(")

