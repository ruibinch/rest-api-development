import json
import unittest
import pymongo
from pymongo import MongoClient
from bson import ObjectId
import mongoengine
import uuid

class AppTestCase(unittest.TestCase):

    def setUp(self):
        app.app.testing = True
        self.app = app.app.test_client()
        def post_json(path='/', **kwargs):
            if 'json' in kwargs:
                kwargs['data'] = json.dumps(kwargs['json'])
                kwargs['content_type'] = 'application/json'
                del kwargs['json']
            return old_post(path, **kwargs)
        old_post, self.app.post = self.app.post, post_json
        self.testUsername = 'test-' + str(uuid.uuid4())

    def tearDown(self):
        with Db(app) as db:
            schema.User.objects(username = self.testUsername).delete()
            schema.User.objects(fullname = 'Peter Test').delete()
            schema.Post.objects(title = self.testUsername, text = "this is a test post").delete()

    def test_db_setup(self):
        client = MongoClient(config.db_host, config.db_port)
        #test initial state of the database
        try:
            self.assertIn('local', client.database_names())
            self.assertNotIn('test_db', client.database_names())
            #test insertion of an entry
            db = client.test_db
            collection = db.test_collection
            entry = {'text' : 'test'}
            _id = collection.insert_one(entry).inserted_id
            self.assertEqual(collection.find_one({'_id': ObjectId(_id)})['text'], 'test')
            #test creation of the test database
            self.assertIn('test_db', client.database_names())
            #test removal of the entry
            collection.remove({'_id': ObjectId(_id)})
            self.assertIsNone(collection.find_one({'_id': ObjectId(_id)}))
            #test removal of the test database
            db.test_collection.drop()
            client.drop_database('test_db')
            self.assertNotIn('test_db', client.database_names())
        except pymongo.errors.OperationFailure as e:
            print "Skipping test_db_setup:", str(e)
        client.close()

    def test_db_register_user(self):
        with Db(app) as db:
            db.registerUser(username = self.testUsername, fullname = 'testuser', password = 'test', age = 20)
            result = schema.User.objects(username = self.testUsername, fullname = 'testuser', age = 20)
            # one exact match should be found
            self.assertEqual(len(result), 1)
            schema.User.objects(username = self.testUsername, fullname = 'testuser', age = 20).delete()
            result = schema.User.objects(username = self.testUsername, fullname = 'testuser', age = 20)
            # no match should be found
            self.assertFalse(result)

    def test_db_insert_post(self):
        with Db(app) as db:
            db.registerUser(username = self.testUsername, fullname = 'testuser', password = 'test', age = 20)
            user = schema.User.objects(username = self.testUsername, fullname = 'testuser', age = 20)[0]
            db.insertPost(user, self.testUsername, True, "this is a test post")
            result = schema.Post.objects(author = user, public = True,
                title = self.testUsername, text = "this is a test post")
            # one exact match should be found
            self.assertEqual(len(result), 1)
            schema.Post.objects(author = user, public = True,
                title = self.testUsername, text = "this is a test post").delete()
            result = schema.Post.objects(author = user, public = True,
                title = self.testUsername, text = "this is a test post")
            # no match should be found
            self.assertFalse(result)
            schema.User.objects(username = self.testUsername, fullname = 'testuser', age = 20).delete()

    def test_index(self):
        index = self.app.get('/')
        self.assertEqual(index.status_code, 200)
        response = json.loads(index.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertTrue(response['status'])
        self.assertTrue(response.has_key('result'))
        self.assertIsInstance(response['result'], list)

    def test_meta_heartbeat(self):
        meta_heartbeat = self.app.get('/meta/heartbeat')
        self.assertEqual(meta_heartbeat.status_code, 200)
        response = json.loads(meta_heartbeat.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertTrue(response['status'])

    def test_meta_members(self):
        meta_members = self.app.get('/meta/members')
        self.assertEqual(meta_members.status_code, 200)
        response = json.loads(meta_members.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertTrue(response['status'])
        self.assertTrue(response.has_key('result'))
        self.assertIsInstance(response['result'], list)

    def test_users(self):
        testUsername = 'test-' + str(uuid.uuid4())
        testFullname = "Peter Test"
        testAge = 20
        body = {"username": testUsername, "password": "pass", "fullname": testFullname, "age": testAge}
        # Register new user
        users_register = self.app.post('/users/register', json=body)
        self.assertEqual(users_register.status_code, 201)
        response = json.loads(users_register.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertTrue(response['status'])
        # Register same user
        users_register = self.app.post('/users/register', json=body)
        self.assertEqual(users_register.status_code, 200)
        response = json.loads(users_register.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertFalse(response['status'])
        # Authenticate the registered user
        users_authenticate = self.app.post('/users/authenticate', json=body)
        self.assertEqual(users_authenticate.status_code, 200)
        response = json.loads(users_authenticate.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertTrue(response['status'])
        self.assertTrue(response.has_key('token'))
        self.assertIsInstance(response['token'], basestring)
        token = response['token']
        body = {"token": token}
        # Retrieve authenticated user
        users = self.app.post('/users', json=body)
        self.assertEqual(users.status_code, 200)
        response = json.loads(users.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertTrue(response['status'])
        self.assertTrue(response.has_key('username'))
        self.assertTrue(response.has_key('fullname'))
        self.assertTrue(response.has_key('age'))
        self.assertEqual(response['username'], testUsername)
        self.assertEqual(response['fullname'], testFullname)
        self.assertEqual(response['age'], testAge)
        # Expire authenticated token
        users_expire = self.app.post('/users/expire', json=body)
        self.assertEqual(users_expire.status_code, 200)
        response = json.loads(users_expire.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertTrue(response['status'])
        # Assert invalidated token
        users = self.app.post('/users', json=body)
        self.assertEqual(users.status_code, 200)
        response = json.loads(users.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertFalse(response['status'])

    def test_users_bogus(self):
        body = {"username": "bogus", "password": "bogus"}
        # Authenticate bogus user
        users_authenticate = self.app.post('/users/authenticate', json=body)
        self.assertEqual(users_authenticate.status_code, 200)
        response = json.loads(users_authenticate.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertFalse(response['status'])
        body = {"token": "bogus"}
        # Retrieve user with bogus token
        users = self.app.post('/users', json=body)
        self.assertEqual(users.status_code, 200)
        response = json.loads(users.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertFalse(response['status'])
        # Expire bogus token
        users_expire = self.app.post('/users/expire', json=body)
        self.assertEqual(users_expire.status_code, 200)
        response = json.loads(users_expire.get_data())
        self.assertTrue(response.has_key('status'))
        self.assertFalse(response['status'])

    def test_diary(self):
        pass

    def test_diary_create(self):
        pass

    def test_diary_delete(self):
        pass

    def test_diary_permission(self):
        pass


if __package__ is None:
    import sys
    from os import path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))
    from service import app, db_transaction_api, schema, config
else:
    from ..service import app, db_transaction_api, schema, config
Db = db_transaction_api.Db

if __name__ == '__main__':
    unittest.main()