from django.test import TestCase, Client
from channels.testing import ChannelsLiveServerTestCase

from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys

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


class Browser:
    def __init__(self, live_server_url):
        profile = Options()
        profile.set_preference('intl.accept_languages', 'en-us')
        profile.set_preference("dom.disable_beforeunload", True)
        self._x = WebDriver(options=profile)
        self._x.set_window_position(0, 0)
        self._x.set_window_size(1920, 1080)
        self._live_server_url = live_server_url

    def quit(self):
        self._x.quit()

    def get(self, url) -> 'Browser':
        if url.startswith('/'):
            url = self._live_server_url + url
        self._x.get(url)
        return self

    def click_link(self, text: str) -> 'Browser':
        self._x.find_element_by_link_text(text).click()
        return self

    def click(self, what: str) -> 'Browser':
        if isinstance(what, str):
            what = self.select(what)
        what.click()
        return self

    def select(self, css_selector) -> WebElement:
        return self.wait_for(css_selector)

    def select_many(self, css_selector) -> [WebDriver]:
        return self.wait_for(
            lambda x: x.find_elements_by_css_selector(css_selector)
        )

    def wait_for(self, predicate, timeout=1, poll_frequency=0.1):
        if isinstance(predicate, str):
            _predicate = lambda x: x.find_element_by_css_selector(predicate) # noqa
        else:
            _predicate = predicate

        return WebDriverWait(self._x, timeout, poll_frequency).until(_predicate)

    def hold_until_gone(self, predicate, timeout=1, poll_frequency=0.1):
        if isinstance(predicate, str):
            _predicate = lambda x: not x.find_element_by_css_selector(predicate) # noqa
        else:
            _predicate = predicate

        return WebDriverWait(self._x, timeout, poll_frequency).until_not(
            _predicate
        )

    def focused(self) -> WebElement:
        return self._x.switch_to.active_element

    def chain(self):
        return ActionChains(self._x)


class SeleniumTests(ChannelsLiveServerTestCase):

    def setUp(self):
        super().setUpClass()
        self.x = Browser(self.live_server_url)

    def tearDown(self):
        self.x.quit()
        super().tearDown()

    def test_click(self):
        # Navigate to todo app
        new_item_input = (
            self.x
            .get('/')
            .click_link('todo view')
            .focused()
        )

        # Add first task
        new_item_input.send_keys(f'HI{Keys.ENTER}')
        assert not new_item_input.text
        assert self.x.select('[is=x-todo-item]').text == 'HI'
        counter = self.x.select('[is=x-todo-counter]')
        assert counter.text == '1 item left'

        # Add second task
        new_item_input.send_keys(f'Second task{Keys.ENTER}')
        self.x.wait_for(
            lambda _:
                not new_item_input.text
                and len(self.x.select_many('[is=x-todo-item]')) == 2
        )
        todo_items = self.x.select_many('[is=x-todo-item]')
        assert todo_items[0].text == 'HI'
        assert todo_items[1].text == 'Second task'
        assert counter.text == '2 items left'

        # Mark second task as done
        second_task = todo_items[1]
        second_task.select('[name=completed]').click()
        self.x.wait_for(
            lambda _: second_task.select('li').has_class('completed')
        )
        assert counter.text == '1 item left'

        # Show active items
        self.x.click_link('Active')
        self.x.wait_for(lambda _: second_task['li'].has_class('hidden'))
        first_task = todo_items[0]
        assert not first_task['li'].has_class('hidden')

        # Show completed items
        self.x.click_link('Completed')
        self.x.wait_for(lambda _: first_task['li'].has_class('hidden'))
        assert not second_task['li'].has_class('hidden')

        # Show all
        self.x.click_link('All')
        self.x.wait_for(
            lambda _:
                not first_task['li'].has_class('hidden')
                and not second_task['li'].has_class('hidden')
        )

        # Clear completed tasks
        self.x.select('button.clear-completed').click()
        self.x.wait_for(
            lambda _: len(self.x.select_many('[is=x-todo-item]')) == 1
        )
        assert self.x.select_many('[is=x-todo-item]') == [first_task]

        # Edit the first task.
        first_task['label'].click()
        first_task_input = self.x.wait_for(lambda _: first_task['input.edit'])
        assert first_task_input == self.x.focused()
        first_task_input.send_keys(
            f'{Keys.BACKSPACE}{Keys.BACKSPACE}First item{Keys.ENTER}'
        )

        self.x.hold_until_gone(lambda _: first_task['.editing'])
        (
            self.x.chain()
            .move_to_element(first_task['label'])
            .click(first_task['.destroy'])
            .perform()
        )
        self.x.hold_until_gone('[is=x-todo-item]')


def classes(element: WebElement) -> set:
    return set(element.get_attribute('class').split())


def has_class(element: WebElement, class_name) -> WebElement:
    return class_name in element.classes


def select(element: WebElement, css_selector: str) -> WebElement:
    return element.find_element_by_css_selector(css_selector)


def select_many(element: WebElement, css_selector: str) -> WebElement:
    return element.find_elements_by_css_selector(css_selector)


WebElement.classes = property(classes)
WebElement.has_class = has_class
WebElement.select = select
WebElement.__getitem__ = select
WebElement.select_many = select_many
