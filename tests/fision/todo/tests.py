import asyncio
import threading
from os import environ as env
from random import randint
from urllib.parse import urljoin
from time import sleep

from uvicorn.main import Server as Uvicorn
from uvicorn.config import Config as UvicornConfig

from django.test import TestCase, TransactionTestCase, Client, override_settings
from channels.routing import get_default_application

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from splinter import Browser
from splinter.element_list import ElementList
from splinter.driver import ElementAPI
from splinter.driver.webdriver import WebDriverElement
from splinter.driver.webdriver.firefox import WebDriver as FirefoxDriver
from splinter.driver.lxmldriver import LxmlDriver
from splinter.driver.djangoclient import DjangoClient as DjangoDriver

from .models import Item


class TestNormalRendering(TestCase):

    def setUp(self):
        Item.objects.create(text='First task')
        Item.objects.create(text='Second task')
        self.c = Client()

    def test_everything_two_tasks_are_rendered(self):
        response = self.c.get('/todo')
        assert response.status_code == 200
        self.assertContains(response, 'First task')
        self.assertContains(response, 'Second task')


# HACK: https://github.com/cobrateam/splinter/pull/820

def submit(self: LxmlDriver, form):
    method = form.attrib.get("method", "get").lower()
    action = form.attrib.get("action", "")
    if action.strip() not in (".", ""):
        url = urljoin(self._url, action)
    else:
        url = self._url
    self._url = url
    data = self.serialize(form)

    self._do_method(method, url, data=data)
    return self._response


LxmlDriver.submit = submit


class UvicornThread(threading.Thread):

    def __init__(self, application, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.application = application
        self.server = None

    @override_settings(DEBUG=True)
    def run(self):
        self.loop = asyncio.new_event_loop()
        config = UvicornConfig(self.application, host=self.host, port=self.port)
        self.server = Uvicorn(config)
        self.server.install_signal_handlers = lambda *args, **kwargs: None
        self.loop.run_until_complete(self.server.serve())
        self.server = None

    @property
    def started(self):
        return self.server and self.server.started

    def terminate(self):
        self.server.force_exit = True
        self.server.should_exit = True
        self.loop.create_task(self.server.shutdown())


class TestMixin:

    driver_type = 'django'
    x: DjangoDriver

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        headless = not env.get('DISPLAY')
        cls.x = Browser(
            cls.driver_type,
            headless=headless,
            wait_time=10 if headless else 2
        )

    @classmethod
    def tearDownClass(cls):
        cls.x.quit()
        super().tearDownClass()

    def print_html(self):
        from pygments import highlight
        from pygments.lexers import HtmlLexer
        from pygments.formatters import TerminalTrueColorFormatter
        print(highlight(
            self.x.html,
            HtmlLexer(),
            TerminalTrueColorFormatter()
        ))


class ChannelsLiveServerTestCase(TestMixin, TransactionTestCase):
    host = '127.0.0.1'
    driver_type = 'firefox'
    x: FirefoxDriver

    @property
    def live_server_url(self):
        return "http://%s:%s" % (self.host, self._port)

    def scroll_into_view(self, element):
        if isinstance(element, ElementList):
            element = element[0]

        if isinstance(element, ElementAPI):
            element = element._element

        self.x.execute_script('arguments[0].scrollIntoView(true);', element)

    def _pre_setup(self):
        super()._pre_setup()
        self._port = randint(9000, 40000)
        self._server = UvicornThread(
            get_default_application(),
            self.host,
            self._port,
        )
        self._server.start()
        while not self._server.started:
            sleep(0.1)

    def _post_teardown(self):
        self._server.terminate()
        # Nah... it's fine... don't wait, live is too short..
        # speed over correctness!
        # self._server.join()
        super()._post_teardown()

    def assert_focused(self, element):
        return element._element == self.x.driver.switch_to.active_element

    def chain(self):
        return ActionChains(self.x.driver)

    def send_ctrl(self, key):
        (
            self.chain()
            .key_down(Keys.CONTROL)
            .send_keys(key)
            .key_up(Keys.CONTROL)
            .perform()
        )


class SeleniumTests(ChannelsLiveServerTestCase):

    def test_click(self):
        # Navigate to todo app
        self.x.visit(self.live_server_url)
        self.x.click_link_by_text('todo view')

        new_item_input = self.x.find_by_tag('input')[0]
        # Add first task
        new_item_input._element.send_keys(f'HI{Keys.ENTER}')
        assert not new_item_input.text
        assert self.x.find_by_css('[is=x-todo-item]').text == 'HI'
        counter = self.x.find_by_css('[is=x-todo-counter]')
        assert counter.text == '1 item left'

        # Add second task
        new_item_input._element.send_keys(f'Second task{Keys.ENTER}')
        sleep(0.1)
        todo_items = self.x.find_by_css('[is=x-todo-item]')
        assert todo_items[0].text == 'HI'
        assert todo_items[1].text == 'Second task'
        assert counter.text == '2 items left'

        # Mark second task as done
        second_task: WebDriverElement = todo_items[1]
        second_task.find_by_css('[name=completed]').click()
        assert self.x.is_element_present_by_css('li.completed')
        assert counter.text == '1 item left'

        # Show active items
        self.x.click_link_by_partial_text('Active')
        assert second_task.find_by_css('li.hidden')
        first_task: WebDriverElement = todo_items[0]
        assert not first_task.find_by_css('li').has_class('hidden')

        # Show completed items
        self.x.click_link_by_partial_text('Completed')
        assert first_task.find_by_css('li.hidden')
        assert not second_task.find_by_css('li').has_class('hidden')

        # Show all
        self.x.click_link_by_partial_text('All')
        assert self.x.is_element_not_present_by_css('li.hidden')

        # Clear completed tasks
        self.x.find_by_css('button.clear-completed').click()
        items = self.x.find_by_css('[is=x-todo-item]')
        assert len(items) == 1
        assert items['id'] == first_task['id']

        # Edit the first task.
        first_task.find_by_tag('label').click()
        first_task_input = first_task.find_by_css('input.edit')
        assert self.assert_focused(first_task_input)
        self.send_ctrl('a')
        first_task_input._element.send_keys(
            f'{Keys.BACKSPACE}First item{Keys.ENTER}'
        )

        assert self.x.is_element_not_present_by_css('li .editing')
        first_task.find_by_css('.destroy').click()
        assert self.x.is_element_not_present_by_css('[is=x-todo-item]')
