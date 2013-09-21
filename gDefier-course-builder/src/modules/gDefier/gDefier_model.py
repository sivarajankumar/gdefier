"""Common classes and methods for managing GDefier modules."""

__author__ = 'Diego Garcia (diego.gmartin@alumnos.uc3m.es)'

import yaml
import logging

from common.schema_fields import FieldRegistry
from common.schema_fields import SchemaField

# Here are the defaults for a G-Defier module of a new course.
DEFAULT_COURSE_GDEFIER_DICT = {
    'course': {
       'title': 'UNTITLED COURSE',
       'module_weight' : 5,
       'n_blocks' : 3,
       'blocks_weight': [2,2,2,2,2],
       'n_challenges' : 3,
       'rally_block' : True,
       'n_rally' : 10,
       'editor_block' : True,
       'n_editor' : 5,
       'cast1' : '',
       'cast2' : '',
       'cast3' : '',       
      }                  
}

def create_gdefier_module_registry():
    """Create the registry for course properties."""

    reg = FieldRegistry('G-Defier Module Settings', description='G-Defier Settings')

    # Module settings.
    module_opts = reg.add_sub_registry('course', 'Module Config')
    module_opts.add_property(SchemaField(
        'course:module_weight', 'Module Weight', 'integer'))
    module_opts.add_property(SchemaField(
        'course:n_blocks', 'Number of blocks', 'integer'))
    module_opts.add_property(SchemaField(
        'course:n_challenges', 'Challenges', 'integer',
        description='Number of challenges to pass the blocks'))
    module_opts.add_property(SchemaField(
         'course:rally_block', 'Make Rally block active', 'boolean'))
    module_opts.add_property(SchemaField(
         'course:n_rally', 'Rally size', 'integer',
         description='Number of questions in a row to get Rally block'))
    module_opts.add_property(SchemaField(
        'course:editor_block', 'Make Editor block active', 'boolean'))
    module_opts.add_property(SchemaField(
        'course:n_editor', 'Exercises to upload', 'integer',
        description='Minimun Number of exercises to upload necessary to get Editor block'))
    module_opts.add_property(SchemaField(
        'course:blocks_weight', 'Blocks weight', 'array',
        description="Weight assigned to each block.")) #Example HOWTO write it:"
#" case 3 blocks & all modes ON (rally & editor) [x,x,x,x,x];"
#" case 2 blocks & no modules actived [x,x]."
#" The Xs represent numbers and its sum should be 10."))

    # Question to each block.
    cast_opts = reg.add_sub_registry('Questions Cast', 'Cast of questions')
    cast_opts.add_property(SchemaField(
        'course:cast1', 'Question IDs to block 1', 'html', optional=True))
    cast_opts.add_property(SchemaField(
        'course:cast2', 'Question IDs to block 2', 'html', optional=True))
    cast_opts.add_property(SchemaField(
        'course:cast3', 'Question IDs to block 3', 'html', optional=True))
    return reg