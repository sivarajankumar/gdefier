"""Common classes and methods for managing GDefier modules."""

__author__ = 'Diego Garcia (diego.gmartin@alumnos.uc3m.es)'

import zipfile

from common import tags
from common import schema_fields

from common.schema_fields import FieldRegistry
from common.schema_fields import SchemaField

from controllers import sites

from modules.khanex import khanex

from google.appengine.ext import db

# Here are the defaults for a G-Defier module of a new course.
DEFAULT_COURSE_GDEFIER_DICT = {
    'module': {
       'w_module' : 6,
       'n_blocks' : 1,
       'n_challenges' : 3,
       'rally_block' : True,
       'n_rally' : 10,
       'w_rally' : 2,
       'editor_block' : True,
       'n_editor' : 5,
       'w_editor' : 2     
      }                  
}

DATE_FORMAT_DESCRIPTION = """
Should be formatted as YYYY-MM-DD hh:mm (e.g. 1997-07-16 19:20) and be specified
in the UTC timezone."""

def create_gdefier_module_registry():
    """Create the registry for course properties."""
    
    """Make schema with a list of all exercises by inspecting a zip file."""
    zip_file = zipfile.ZipFile(khanex.ZIP_FILE)
    exercise_list = []
    for name in zip_file.namelist():
        if name.startswith(khanex.EXERCISE_BASE) and name != khanex.EXERCISE_BASE:
            exercise_list.append(name[len(khanex.EXERCISE_BASE):])
    khanex_exercises = []
    index = 1
    for url in sorted(exercise_list):
        name = url.replace('.html', '')
        if khanex._allowed(name):
            caption = name.replace('_', ' ')
            khanex_exercises.append((name, '#%s: %s' % (index, caption)))
            index += 1

    reg = FieldRegistry('G-Defier Module Settings', description='G-Defier Settings')

    # Module settings.
    module_opts = reg.add_sub_registry('module', 'Module Config')
    module_opts.add_property(SchemaField(
        'module:w_module', 'Module Weight', 'integer'))
    
    n_blocks_options = []
    n_blocks_options.append((1, 1))
    n_blocks_options.append((2, 2))
    n_blocks_options.append((3, 3))
    
    module_opts.add_property(SchemaField(
        'module:n_blocks', 'Number of blocks', 'integer', select_data=n_blocks_options))
    module_opts.add_property(SchemaField(
        'module:n_defies', 'Defies', 'integer',
        description='Number of defies to pass the blocks'))
    module_opts.add_property(SchemaField(
        'module:max_defies', 'Max Defies', 'integer',
        description='Maximum number of playble defies in a block to get its score'))
    module_opts.add_property(SchemaField(
        'module:rally_block', 'Make Rally block active', 'boolean'))
    module_opts.add_property(SchemaField(
        'module:w_rally', 'Rally Weight', 'integer'))    
    module_opts.add_property(SchemaField(
        'module:n_rally', 'Rally size', 'integer',
         description='Number of questions in a row to get Rally block'))
    module_opts.add_property(SchemaField(
        'module:editor_block', 'Make Editor block active', 'boolean'))
    module_opts.add_property(SchemaField(
        'module:w_editor', 'Editor Weight', 'integer'))    
    module_opts.add_property(SchemaField(
        'module:n_editor', 'Exercises to upload', 'integer',
        description='Minimum Number of exercises to upload necessary to get Editor block'))

    defy_type = module_opts.add_sub_registry('defy', 'Defy config')

    defy_type.add_property(SchemaField(
        'module:defy:n_round', 'Number of rounds', 'integer',
        description='Number of rounds into each defy')) 
    defy_type.add_property(SchemaField(
        'module:defy:time2accept', 'Time 2 accept', 'integer',
        description='Time in hours to accept a defy request'))
    defy_type.add_property(SchemaField(
        'module:defy:round_time', 'Round time', 'integer',
        description='Time in minutes to respond into each round'))
    
    block_type = schema_fields.FieldRegistry(
            'Question Block',
            extra_schema_dict_values={'className': 'sa-grader'})
    block_type.add_property(schema_fields.SchemaField(
        'block_title', 'Block Title', 'string',
        extra_schema_dict_values={'className': 'inputEx-Field content'}))
    block_type.add_property(schema_fields.SchemaField(
        'w_block', 'Block Weight', 'integer',
        extra_schema_dict_values={'className': 'inputEx-Field content'}))
    block_type.add_property(schema_fields.SchemaField(
        'gdf_start_date', 'Start date', 'string',
        extra_schema_dict_values={'className': 'inputEx-Field content'},
        description=str(DATE_FORMAT_DESCRIPTION)))
    block_type.add_property(schema_fields.SchemaField(
        'gdf_close_date', 'Deadline', 'string',
        extra_schema_dict_values={'className': 'inputEx-Field content'},
        description=str(DATE_FORMAT_DESCRIPTION)))
    block_type.add_property(schema_fields.SchemaField(
        'question_cast', 'Question cast', 'html', optional=True,
        extra_schema_dict_values={
            'supportCustomTags': tags.CAN_USE_DYNAMIC_TAGS.value,
            'excludedCustomTags': tags.EditorBlacklists.ASSESSMENT_SCOPE,
            'className': 'inputEx-Field html-content'}))

    blocks_array = schema_fields.FieldArray(
        'module:blocks', 'Blocks for the course', item_type=block_type,
        extra_schema_dict_values={
            'className': 'sa-grader-container',
            #'sortable': 'true',
            'listAddLabel': 'Add a block',
            'listRemoveLabel': 'Delete this block'})

    module_opts.add_property(blocks_array)
    
    return reg

class GDefierGroup(db.Model):
    name = db.StringProperty(indexed=True, required=True)
    @property
    def members(self):
        return GDefierPlayer.gql("WHERE group = :1", self.key())

class GDefierPlayer(db.Model):
    name = db.StringProperty(indexed=True, required=True)
    total_score = db.IntegerProperty(indexed=True, required=True, default=0)
    
    """r_on = db.BooleanProperty(indexed=False, default=False)
    r_count = db.IntegerProperty(indexed=False, default=0)
    r_done = db.BooleanProperty(indexed=False, default=False)
    e_on = db.BooleanProperty(indexed=False, default=False)
    e_rallies = db.ListProperty(int)
    e_done = db.BooleanProperty(indexed=False, default=False)"""
    
    # Group affiliation
    group = db.ListProperty(db.Key)
        

class GDefierBlock(db.Model):
    player = db.ReferenceProperty(GDefierPlayer,
                               collection_name='blocks')
    blockID = db.StringProperty(indexed=True, required=True)
    activated = db.BooleanProperty(indexed=False, default=False)
    done = db.BooleanProperty(indexed=False, default=False)
    wins = db.IntegerProperty(indexed=False, default=0)
    lost = db.IntegerProperty(indexed=False, default=0)
    request = db.ListProperty(str)
    sends = db.ListProperty(str)
    
class GDefierBoard(db.Model):
    name = db.StringProperty(indexed=True, required=True)  
    @property
    def members(self):
        return GDefierDefy.gql("WHERE board = :1", self.key())
    
class GDefierBoardBlock(db.Model):
    blockID = db.StringProperty(indexed=True, required=True)  
    # Board affiliation
    board = db.ListProperty(db.Key)

class GDefierDefy(db.Model):
    board = db.ReferenceProperty(GDefierBoardBlock,
                           collection_name='defies')
    rname = db.StringProperty(indexed=True, required=True)
    lname = db.StringProperty(indexed=True, required=True)
    turn = db.StringProperty(indexed=True, required=True,
                             choices=set(["r","l"]))
    rscore = db.IntegerProperty(indexed=False, default=0)
    lscore = db.IntegerProperty(indexed=False, default=0)
    rtime = db.TimeProperty(indexed=False)
    ltime = db.TimeProperty(indexed=False)
 
def create_player(self):
    nick = self.get_user().nickname()
    alumn = GDefierPlayer.gql("WHERE name = '" + nick +"'").get()
    if not alumn:
        print "user created"
        #Creating and adding to correspondent group
        course = sites.get_course_for_current_request()
        aux_group = GDefierGroup.gql("WHERE name = '" + course.get_namespace_name() + "'").get()
        if not aux_group:
            print "First player..."
            aux_group = create_group(self)
        else:
            aux_group=aux_group.key()
        GDefierPlayer(name=nick, group=[aux_group]).put()
        
def delete_player(self):
    nick = self.get_user().nickname()
    alumn = GDefierPlayer.gql("WHERE name = '" + nick +"'").get()
    if alumn:
        print "Deleting player..."
        print "Player with blocks?"
        for block in alumn.blocks:
            "Deleting blocks..."
            delete_block(self, block.blockID)
        alumn.delete()

def add_block_to_player(self, block_ID):
    nick = self.get_user().nickname()
    alumn = GDefierPlayer.gql("WHERE name = '" + nick +"'").get()
    for b in alumn.blocks:
        if b.blockID == block_ID:
            #print "Block already added..."
            return b
    print "Adding block to player..."
    block = GDefierBlock(player=alumn, blockID=block_ID).put()
    return block

def delete_block(self, block_ID):
    nick = self.get_user().nickname()
    alumn = GDefierPlayer.gql("WHERE name = '" + nick +"'").get()
    for b in alumn.blocks:
        if b.blockID == block_ID:
            print "Deleting block with ID -->", b.blockID
            b.delete()

def create_group(self):
    course = sites.get_course_for_current_request()
    group = GDefierGroup.gql("WHERE name = '" + course.get_namespace_name() + "'").get()
    if not group:
        print "Creating group..." 
        aux_group = GDefierGroup(name=course.get_namespace_name()).put()
        return aux_group
    return group
    
def get_players(self):
    course = sites.get_course_for_current_request().get_namespace_name()
    results = db.GqlQuery("SELECT * FROM GDefierGroup WHERE name ='"+course+"'")
    for x in results:
        players = x.members
        return players

def player_exist(self):
    nick = self.get_user().nickname()
    alumn = GDefierPlayer.gql("WHERE name = '" + nick +"'").get()
    if not alumn:
        return True
    return False

def player_has_blocks(self):
    nick = self.get_user().nickname()
    alumn = GDefierPlayer.gql("WHERE name = '" + nick +"'").get()
    if alumn.blocks.count() != 0:
        return False
    return True        

def to_dict(self):
    return dict([(p, unicode(getattr(self, p))) for p in self.properties()])

def add_request_challenge(self, user, block_ID):
    nick = self.get_user().nickname()
    alumn = GDefierPlayer.gql("WHERE name = '" + nick +"'").get()
    for b in alumn.blocks:
        if b.blockID == block_ID:
            print "xxxxxxx"
            b.sends.append(user)
            b.put()
            break
    alumn = GDefierPlayer.gql("WHERE name = '" + user +"'").get()
    for b in alumn.blocks:
        if b.blockID == block_ID:
            print "yyyyyyyy"
            b.request.append(nick)
            b.put()
            break

def create_board(self, blocks):
    course = sites.get_course_for_current_request()
    board = GDefierBoard.gql("WHERE name = '" + course.get_namespace_name() + "'").get()
    if not board:
        print "Creating board..." 
        aux_board = GDefierBoard(name=course.get_namespace_name()).put()
        for b in blocks:
            print "Creating block to board..." 
            GDefierBoardBlock(blockID=b['block_title'], board=[aux_board]).put()        
        return aux_board
    return board