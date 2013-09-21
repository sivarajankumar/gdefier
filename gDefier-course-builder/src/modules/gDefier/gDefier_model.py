"""Common classes and methods for managing GDefier modules."""

__author__ = 'Diego Garcia (diego.gmartin@alumnos.uc3m.es)'

import os
import zipfile

from common import schema_fields
from common.schema_fields import FieldRegistry
from common.schema_fields import SchemaField
from modules.khanex import khanex

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
        'module:n_challenges', 'Challenges', 'integer',
        description='Number of challenges to pass the blocks'))
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
        description='Minimun Number of exercises to upload necessary to get Editor block'))
    
    block_type = schema_fields.FieldRegistry(
            'Question Block',
            extra_schema_dict_values={'className': 'sa-grader'})
    block_type.add_property(schema_fields.SchemaField(
        'block_title', 'Block Title', 'string',
        extra_schema_dict_values={'className': 'sa-grader-text'}))
    block_type.add_property(schema_fields.SchemaField(
        'w_editor', 'Block Weight', 'integer',
        extra_schema_dict_values={'className': 'sa-grader-text'}))
    block_type.add_property(schema_fields.SchemaField(
        'gdf_start_date', 'Start date', 'string',
        extra_schema_dict_values={'className': 'sa-grader-text'},
        description=str(DATE_FORMAT_DESCRIPTION)))
    block_type.add_property(schema_fields.SchemaField(
        'gdf_close_date', 'Deadline', 'string',
        extra_schema_dict_values={'className': 'sa-grader-text'},
        description=str(DATE_FORMAT_DESCRIPTION)))
    block_type.add_property(schema_fields.SchemaField(
        'question_cast', 'Question cast', 'html', optional=True,
        extra_schema_dict_values={'className': 'sa-grader-feedback'}))

    blocks_array = schema_fields.FieldArray(
        'module:blocks', 'Blocks for the course', item_type=block_type,
        extra_schema_dict_values={
            'className': 'sa-grader-container',
            'listAddLabel': 'Add a block',
            'listRemoveLabel': 'Delete this block'})

    module_opts.add_property(blocks_array)
    
    return reg