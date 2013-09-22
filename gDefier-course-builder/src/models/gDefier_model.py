"""Common classes and methods for managing GDefier modules."""

__author__ = 'Diego Garcia (diego.gmartin@alumnos.uc3m.es)'

import zipfile
import models
from models import MemcacheManager
import progress
import review
import transforms
import vfs

from common import tags
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
        extra_schema_dict_values={'className': 'inputEx-Field content'}))
    block_type.add_property(schema_fields.SchemaField(
        'w_editor', 'Block Weight', 'integer',
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

class GDefier(object):
    """Manages a G-Defier module and all of its components."""

    @classmethod
    def get_environ(cls, app_context):
        """Returns currently defined course settings as a dictionary."""
        pass


    @classmethod
    def _load(cls, app_context):
        """Loads course data from persistence storage into this instance."""
        pass

    def __init__(self, handler, app_context=None):
        self._app_context = app_context if app_context else handler.app_context
        self._namespace = self._app_context.get_namespace_name()
        self._model = self._load(self._app_context)
        self._tracker = None
        self._reviews_processor = None

    @property
    def app_context(self):
        return self._app_context

    def to_json(self):
        return self._model.to_json()

    def save(self):
        return self._model.save()

    def get_score(self, student, assessment_id):
        """Gets a student's score for a particular assessment."""
        assert self.is_valid_assessment_id(assessment_id)
        scores = transforms.loads(student.scores) if student.scores else {}
        return scores.get(assessment_id) if scores else None

    def get_overall_score(self, student):
        """Gets the overall course score for a student."""
        score_list = self.get_all_scores(student)
        overall_score = 0
        total_weight = 0
        for unit in score_list:
            if not unit['human_graded']:
                total_weight += unit['weight']
                overall_score += unit['weight'] * unit['score']

        if total_weight == 0:
            return None

        return int(float(overall_score) / total_weight)


    def update_final_grades(self, student):
        """Updates the final grades of the student."""
        if (models.CAN_SHARE_STUDENT_PROFILE.value and
            self.is_course_complete(student)):
            overall_score = self.get_overall_score(student)
            models.StudentProfileDAO.update(
                student.user_id, student.email, final_grade=overall_score)

    def get_overall_result(self, student):
        """Gets the overall result based on a student's score profile."""
        score = self.get_overall_score(student)
        if score is None:
            return None

        # This can be replaced with a custom definition for an overall result
        # string.
        return 'pass' if self.get_overall_score(student) >= 70 else 'fail'

    def get_all_scores(self, student):
        """Gets all score data for a student.

        Args:
            student: the student whose scores should be retrieved.

        Returns:
            an array of dicts, each representing an assessment. Each dict has
            the keys 'id', 'title', 'weight' and 'score' (if available),
            representing the unit id, the assessment title, the weight
            contributed by the assessment to the final score, and the
            assessment score.
        """
        assessment_list = self.get_assessment_list()
        scores = transforms.loads(student.scores) if student.scores else {}

        unit_progress = self.get_progress_tracker().get_unit_progress(student)

        assessment_score_list = []
        for unit in assessment_list:
            # Compute the weight for this assessment.
            weight = 0
            if hasattr(unit, 'weight'):
                weight = unit.weight

            completed = unit_progress[unit.unit_id]

            # If a human-reviewed assessment is completed, ensure that the
            # required reviews have also been completed.
            if completed and self.needs_human_grader(unit):
                reviews = self.get_reviews_processor().get_review_steps_by(
                    unit.unit_id, student.get_key())
                review_min_count = unit.workflow.get_review_min_count()
                if not review.ReviewUtils.has_completed_enough_reviews(
                        reviews, review_min_count):
                    completed = False

            assessment_score_list.append({
                'id': str(unit.unit_id),
                'title': unit.title,
                'weight': weight,
                'completed': completed,
                'human_graded': self.needs_human_grader(unit),
                'score': (scores[str(unit.unit_id)]
                          if str(unit.unit_id) in scores else 0),
            })

        return assessment_score_list