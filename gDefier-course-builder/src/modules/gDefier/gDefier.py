"""gDefier module"""

__author__ = 'Diego Garcia (diego.gmartin@alumnos.uc3m.es)'

import webapp2
import jinja2
import jinja2.exceptions
import os
import pprint
import json
import yaml
import logging
import datetime
import re
import ast
from google.appengine.ext import db

from controllers import utils
from controllers import sites
from controllers.utils import BaseHandler
from controllers.utils import BaseRESTHandler
from controllers.utils import XsrfTokenManager
from controllers.sites import ApplicationContext

from models import models
from models import content
from models import custom_modules
from models import vfs
from models import courses
from models import roles
from models import transforms
from models.courses import deep_dict_merge
from models import gDefier_model

from tools import verify

from modules.oeditor import oeditor

from modules.dashboard import filer
from modules.dashboard import messages
from modules.dashboard.course_settings import CourseSettingsRights

from google.appengine.api import users

GCB_GDEFIER_FOLDER_NAME = os.path.normpath('/modules/gDefier/')
DFR_CONFIG_FILENAME = os.path.normpath('/gDefier.yaml')

custom_module = None

def is_editable_fs(app_context):
    return app_context.fs.impl.__class__ == vfs.DatastoreBackedFileSystem

def get_gDefier_config_filename(self):
        """Returns absolute location of a course configuration file."""
        filename = sites.abspath(self.app_context.get_home_folder(),
                                  DFR_CONFIG_FILENAME)
        return filename
    
def get_course_dict():
        return get_environ2()
    
def get_environ2():
    """Returns currently defined course settings as a dictionary."""
    gDefier_yaml = None
    gDefier_yaml_dict = None
    
    ns = ApplicationContext.get_namespace_name_for_request()
    app_context = sites.get_app_context_for_namespace(ns)

    course_data_filename = sites.abspath(app_context.get_home_folder(), DFR_CONFIG_FILENAME)

    if app_context.fs.isfile(course_data_filename):
        gDefier_yaml = app_context.fs.open(course_data_filename)
    if not gDefier_yaml:
        return deep_dict_merge(gDefier_model.DEFAULT_COURSE_GDEFIER_DICT,
                               [])
    try:
        gDefier_yaml_dict = yaml.safe_load(
            gDefier_yaml.read().decode('utf-8'))
    except Exception as e:  # pylint: disable-msg=broad-except
        logging.info(
            'Error: gDefier.yaml file at %s not accessible, '
            'loading defaults. %s', course_data_filename, e)

    if not gDefier_yaml_dict:
        return deep_dict_merge(gDefier_model.DEFAULT_COURSE_GDEFIER_DICT,
                               [])
    return deep_dict_merge(
        gDefier_yaml_dict, gDefier_model.DEFAULT_COURSE_GDEFIER_DICT)
    
        
class RegisterDefierHandler(BaseHandler):

    def get(self):
        gDefier_model.create_player(self)
        
        course_info = get_course_dict()
        blocks =  course_info['module']['blocks']
        gDefier_model.create_board(self, blocks)
        
        self.redirect('/course#registration_confirmation')
    
    def post(self):
        course_info = get_course_dict()
        blocks =  course_info['module']['blocks']
        if blocks:
            for b in blocks:
                gDefier_model.add_block_to_player(self, b['block_title'])
            self.redirect('/gDefier/home?registered=yes')
        else:
            self.redirect('/gDefier/home')   
        
class BlocksHandler(BaseHandler):
    
    def send_request(self, user, block_title):  
        gDefier_model.add_request_challenge(self, user, block_title)  
        self.redirect('/gDefier/block?title=' + block_title)

    def accept_request(self, user, block_title):  
        gDefier_model.del_request_challenge(self, user, block_title)
        # Create a challenge
        gDefier_model.create_defy(self, user, block_title)
        self.redirect('/gDefier/block?title=' + block_title)

    def reject_request(self, user, block_title):
        gDefier_model.del_request_challenge(self, user, block_title)    
        self.redirect('/gDefier/block?title=' + block_title)
    
    def get(self):
        if not self.personalize_page_and_get_enrolled():
            return
         
        block_title = self.request.get('title')

        course_info = get_course_dict()
        for b in course_info['module']['blocks']:
            if b['block_title'] == block_title:
                b_info = b
 
        # Sending, accepting or rejecting an invitation to create challenge
        if self.request.get('request'):
            self.send_request(self.request.get('request'), block_title)
            
        if self.request.get('accept'):
            self.accept_request(self.request.get('accept'), block_title)

        if self.request.get('reject'):
            self.reject_request(self.request.get('reject'), block_title)

        block = gDefier_model.add_block_to_player(self, block_title)
        
        invitations=[]
        if block.request:
            invitations = block.request

        b_stats = gDefier_model.to_dict(block)
        b_stats.pop('player')
        b_stats.pop('blockID')
        b_info.pop('question_cast')

        path = sites.abspath(self.app_context.get_home_folder(),
                     GCB_GDEFIER_FOLDER_NAME)
        page = 'templates/gDefier_blocks.html'
        
        # Avoiding repeated opponents or defies
        players = gDefier_model.get_players(self)
        board_block = gDefier_model.GDefierBoardBlock.gql("WHERE blockID = '" + block_title + "'").get()
        opponents = []
        s1 = ""
        s2 = ""
        me = self.get_user().nickname()
        for p in players:
            existing_defy = False
            if p.blocks.count() == 0:
                #User unregistered in G-Defier module yet
                continue
            for s1 in block.sends:
                if p.name == s1:
                    break
            for s2 in block.request:
                if p.name == s2:
                    break
            if p.name == s1 or p.name == s2 or p.name == me:
                    continue
            for df in board_block.defies:
                if df.rname == p.name and df.lname == me:
                    existing_defy = True
                    break
                elif df.rname == me and df.lname == p.name:
                    existing_defy = True
                    break
            if existing_defy:
                continue
            opponents.append(p.name)
            
        my_defies = gDefier_model.player_defies(self, block_title)

        template = self.get_template(page, additional_dirs=[path])
        self.template_value['navbar'] = {'gDefier': True}
        self.template_value['b_info'] = b_info
        self.template_value['b_stats'] = b_stats
        self.template_value['players'] = opponents
        self.template_value['invitations'] = invitations
        self.template_value['user'] = self.get_user().nickname()
        self.template_value['my_defies'] = my_defies
        self.render(template)

class ArenaHandler(BaseHandler):
    
    def academy_answer(self, khandata):
        data = models.EventEntity.get(khandata)
        js_data = json.loads(data.data)
        
        # Getting the defy key presented in the location attribute of the model entity
        # Nothing has to be after defy in location...
        defy_key =  js_data['location'].split("defy%253D")[-1]
        defy = db.get(defy_key)
        gDefier_model.answer_solver(self, defy, js_data)
            
    def end_defy(self, defy_key, side, n_defies): 
        defy = db.get(defy_key)
        if side == 'right':
            defy.rended = True
            if defy.lended:
                # Defy completely ENDED (2 sides)
                gDefier_model.defy_solver(self, defy, n_defies)
        else:
            defy.lended = True
            if defy.rended:
                # Defy completely ENDED (2 sides)
                gDefier_model.defy_solver(self, defy, n_defies)
        defy.put()
        self.redirect('/gDefier/arena?defy=' + defy_key)
    
    def post(self):
        button = self.request.get('button')
        side = self.request.get('side')
        defy_key = self.request.get('defy')
        defy = db.get(defy_key)
        if side == 'right':
            defy.rround = int(button)
        else:
            defy.lround = int(button)
        defy.put()
    
    def get(self):
        """Handles GET requests."""
        if not self.personalize_page_and_get_enrolled():
            return

        # Cathing Khan answer
        if self.request.get('khandata'):
            self.academy_answer(self.request.get('khandata'))
            return
        
        defy_key = self.request.get('defy')
        
        course_info = get_course_dict()   
        
        # Cathing END exercise
        if self.request.get('end'):
            self.end_defy(defy_key, self.request.get('end'), course_info['module']['n_defies'])

        defy = gDefier_model.GDefierDefy.get(defy_key)
        
        
        path = sites.abspath(self.app_context.get_home_folder(),
                     GCB_GDEFIER_FOLDER_NAME)
        page = 'templates/gDefier_arena.html'        

        nick = self.get_user().nickname()
        if defy.rname == nick:
            side = 'right'
        elif defy.lname == nick:
            side = 'left'
        else:
            side = None
            # Defy from others users...
            page = 'error.html'
        
        """ Getting rounds per defy and possible questions of this bloc"""
        rounds = course_info['module']['defy']['n_round']
        for b in course_info['module']['blocks']:
            if defy.block_board.blockID == b['block_title']:
                question = b['question_cast']
                break
        question = re.findall('[^>]+>', question)
        questions = [i+j for i,j in zip(question[::2],question[1::2])]
        
        t_round = course_info['module']['defy']['round_time']
        
        print defy.rround
        print defy.lround
        template = self.get_template(page, additional_dirs=[path])
        self.template_value['navbar'] = {'gDefier': True}
        self.template_value['defy'] = defy
        self.template_value['questions'] = questions
        self.template_value['rounds'] = rounds
        self.template_value['t_round'] = t_round
        self.template_value['side'] = side
        self.template_value['self'] = self
        self.render(template)

class StudentDefierHandler(BaseHandler):
    """Handlers of gDefier Module for student workspace"""
    def get(self):
        """Handles GET requests."""
        if not self.personalize_page_and_get_enrolled():
            return
        
        path = sites.abspath(self.app_context.get_home_folder(),
                     GCB_GDEFIER_FOLDER_NAME)
        
        course = sites.get_course_for_current_request()

        if not course.get_slug().split("_")[-1] == "DFR":
            page = 'templates/gDefier_error.html'
            self.template_value['error_code'] = 'disabled_gDefier_module'
            self.template_value['is_dashboard'] = False
        else:
            page = 'templates/gDefier.html'
        
        # Patch to double apparition of registration
        registration = None
        if gDefier_model.player_has_blocks(self):
            if self.request.get('registered')=='yes':
                registration = False
            else:
                registration = True
        else:
            registration = False
            
        entity = get_course_dict()
        player = gDefier_model.get_player(self)
        
        prctng = []
        for b in player.blocks:
            n = int(b.wins*100/entity['module']['n_defies'])
            prctng.append("n"+str(n))
        
        template = self.get_template(page, additional_dirs=[path])
        self.template_value['gDefier_transient_student'] = registration
        self.template_value['navbar'] = {'gDefier': True}
        self.template_value['entity'] = entity
        self.template_value['player'] = player
        self.template_value['prctng'] = prctng
        self.render(template)

class GDefierDashboardHandler(object):
    """Should only be inherited by DashboardHandler, not instantiated."""

    def get_gDefier(self):
        """Renders course indexing view if G-Defier module is enabled."""
        
        template_values = {}
        mc_template_value = {}
        
        course = sites.get_course_for_current_request()
        template_values['page_title'] = self.format_title('GDefier')

        """ Catching url hackers """
        if not course.get_slug().split("_")[-1] == "DFR":
            mc_template_value['is_dashboard'] = True
            mc_template_value['error_code'] = 'disabled_gDefier_module'
            template_values['main_content'] = jinja2.Markup(self.get_template(
                'templates/gDefier_error.html', [os.path.dirname(__file__)]
                ).render(mc_template_value, autoescape=True))
            self.render_page(template_values)        
            return
        
        gDefier_actions = []

        # Enable editing if supported.
        if filer.is_editable_fs(self.app_context):
            gDefier_actions.append({
                'id': 'edit_gDefier_DB',
                'caption': 'Edit',
                'action': self.get_action_url('edit_gDefier_course_settings'),
                'xsrf_token': self.create_xsrf_token(
                    'edit_gDefier_course_settings')})

        # gDefier.yaml file content.
        gDefier_info = []

        yaml_stream = self.app_context.fs.open(get_gDefier_config_filename(self))
        
        if yaml_stream:
            yaml_lines = yaml_stream.read().decode('utf-8')
            for line in yaml_lines.split('\n'):
                gDefier_info.append(line)
        else:
            gDefier_info.append('< empty file >')

        # Prepare template values.
        template_values['sections'] = [
            {
                'title': 'Contents of DATA table from gDefier DB',
                'description': "General settings for G-Defier Module to this course.",
                'actions': gDefier_actions,
                'children': gDefier_info}]

        self.render_page(template_values)

class GDefierSettingsHandler(object):
    """G-Defier settings handler."""

    def post_edit_gDefier_course_settings(self):
        """Handles editing of DATA table from gDefier.db"""
        assert is_editable_fs(self.app_context)

        # Check if gDefier.yaml exists; create if not.
        fs = self.app_context.fs.impl
        course_yaml = fs.physical_to_logical('/gDefier.yaml')

        if not fs.isfile(course_yaml):
            fs.put(course_yaml, vfs.string_to_stream(
                courses.EMPTY_COURSE_YAML % users.get_current_user().email()))
        
        self.redirect(self.get_action_url(
            'edit_gDefier_settings', key='/gDefier.yaml'))

    def get_edit_gDefier_settings(self):
        """Shows DATA config of G-Defier module for this course"""

        key = self.request.get('key')

        exit_url = self.canonicalize_url('/dashboard?action=gDefier')
        rest_url = self.canonicalize_url('/rest/course/gDefier')

        form_html = oeditor.ObjectEditor.get_html_for(
            self,
            GDefierSettingsRESTHandler.REGISTORY.get_json_schema(),
            GDefierSettingsRESTHandler.REGISTORY.get_schema_dict(),
            key, rest_url, exit_url, extra_js_files=['gDefier_questions.js'])
        
        template_values = {}
        template_values['page_title'] = self.format_title('Edit G-Defier Settings')
        template_values['page_description'] = 'These are the settings of this course for G-Defier Module.'
        template_values['main_content'] = form_html
        self.render_page(template_values)
        
class GDefierSettingsRESTHandler(BaseRESTHandler):
    """Provides REST API for a file."""
    
    REGISTORY = gDefier_model.create_gdefier_module_registry()
    
    URI = '/rest/course/gDefier'

    @classmethod
    def validate_content(cls, content):
        yaml.safe_load(content)
    
    def get(self):
        """Handles REST GET verb and returns an object as JSON payload."""
        assert is_editable_fs(self.app_context)

        key = self.request.get('key')

        if not CourseSettingsRights.can_view(self):
            transforms.send_json_response(
                self, 401, 'Access denied.', {'key': key})
            return
        
        # Load data if possible.
        fs = self.app_context.fs.impl
        filename = fs.physical_to_logical(key)

        try:
            stream = fs.get(filename)
        except:  # pylint: disable=bare-except
            stream = None
        if not stream:
            transforms.send_json_response(
                self, 404, 'Object not found.', {'key': key})
            return

        # Prepare data.
        entity = {}
        GDefierSettingsRESTHandler.REGISTORY.convert_entity_to_json_entity(
            get_course_dict(), entity)

        # Render JSON response.
        json_payload = transforms.dict_to_json(
            entity,
            GDefierSettingsRESTHandler.REGISTORY.get_json_schema_dict())

        transforms.send_json_response(
            self, 200, 'Success.',
            payload_dict=json_payload,
            xsrf_token=XsrfTokenManager.create_xsrf_token(
                'basic-course-settings-put'))

    def put(self):
        """Handles REST PUT verb with JSON payload."""
        assert is_editable_fs(self.app_context)

        request = transforms.loads(self.request.get('request'))
        key = request.get('key')

        if not self.assert_xsrf_token_or_fail(
                request, 'basic-course-settings-put', {'key': key}):
            return
        
        if not CourseSettingsRights.can_edit(self):
            transforms.send_json_response(
                self, 401, 'Access denied.', {'key': key})
            return

        payload = request.get('payload')

        request_data = {}
        GDefierSettingsRESTHandler.REGISTORY.convert_json_to_entity(
            transforms.loads(payload), request_data)

        entity = courses.deep_dict_merge(request_data, get_course_dict())
        content = yaml.safe_dump(entity)

        try:
            self.validate_content(content)
            content_stream = vfs.string_to_stream(unicode(content))
        except Exception as e:  # pylint: disable=W0703
            transforms.send_json_response(self, 412, 'Validation error: %s' % e)
            return

        # Store new file content.
        fs = self.app_context.fs.impl
        filename = fs.physical_to_logical(key)
        fs.put(filename, content_stream)

        # Send reply.
        transforms.send_json_response(self, 200, 'Saved.')

def register_module():
    """Registers this module in the registry."""

    # provide parser to verify
    verify.parse_content = content.parse_string_in_scope

    # setup routes
    gDefier_routes = [
        ('/gDefier/home', StudentDefierHandler),
        ('/gDefier/register', RegisterDefierHandler),
        ('/gDefier/block', BlocksHandler),
        ('/gDefier/arena', ArenaHandler)
        ]

    global custom_module
    custom_module = custom_modules.Module(
        'gDefier',
        'A set of pages for using gDefier Module.',
        [], gDefier_routes)
    return custom_module