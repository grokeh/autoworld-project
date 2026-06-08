from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from .models import MyModel

class MyModelTestCase(TestCase):
    def setUp(self):
        # Setup runs before each test
        MyModel.objects.create(name="TestName")

    def test_model_name(self):
        # The actual test
        obj = MyModel.objects.get(name="TestName")
        self.assertEqual(obj.name, "TestName")
