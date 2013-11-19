import rg
import random

_game = None
_myPlayerId = None

def towardFilteredOrCurrent(current_loc, dest_loc, filter_out = ('invalid', 'spawn')):
  loc_dist = [(loc, rg.wdist(loc, dest_loc)) for loc in rg.locs_around(current_loc, filter_out) + [current_loc]]
  loc_dist = sorted(loc_dist, key=lambda x: x[1])
  return loc_dist[0][0]

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

class Chaser:
  def __init__(self, me):
    self.me = me

  def chase(self, robot):
    if rg.wdist(self.me.location, robot.location) <= 1:
      return ['attack', robot.location]

    newLocOrCurrent = towardFilteredOrCurrent(self.me.location, robot.location)

    if newLocOrCurrent != self.me.location:
        if canGoTo(newLocOrCurrent):
          return ['move', newLocOrCurrent]
        else:
          print "Being at %s cannot go to %s chasing robot at %s" % (self.me.location, newLocOrCurrent, robot.location)
          return simpleResolveCollision(self.me, newLocOrCurrent)
  
    print "Is it possible at all? Guarding at %s, chasing robot at %s" % (self.me.location, robot.location)
    return ['guard']

def assignTargets():
  targets = {}
  myRobots = filter(lambda (loc, robot): robot['player_id'] == _myPlayerId, _game['robots'].iteritems())
  enemyRobots = filter(lambda (loc, robot): robot.player_id != _myPlayerId, _game['robots'].iteritems())
  enemies = map(lambda (loc, robot): {'location': loc, 'robot': robot, 'numAttacking': 0}, enemyRobots)

  for (myLoc, myRobot) in myRobots:
    enemy = min(enemies, key=lambda r: (r['numAttacking'], rg.wdist(myLoc, r['location'])))
    targets[myRobot['location']] = enemy['robot']
    enemy['numAttacking'] += 1
    print "DBG: %s" % enemies

  return targets

def calculateMove(robot):
  chaser = Chaser(robot)
  targets = assignTargets()
  return chaser.chase(targets[robot.location])

class Robot:
    def act(self, game):
      global _game
      global _myPlayerId
      _game = game
      _myPlayerId = self.player_id
      move = calculateMove(self)
      print "Calculated move: %s" % move
      return move
