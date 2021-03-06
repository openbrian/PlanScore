import unittest, unittest.mock, os, json, io, gzip, itertools
from osgeo import ogr
import botocore.exceptions
from .. import districts, data, score

should_gzip = itertools.cycle([True, False])

def mock_s3_get_object(Bucket, Key):
    '''
    '''
    path = os.path.join(os.path.dirname(__file__), 'data', Key)
    if not os.path.exists(path):
        raise botocore.exceptions.ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
    with open(path, 'rb') as file:
        if next(should_gzip):
            return {'Body': io.BytesIO(gzip.compress(file.read())),
                'ContentEncoding': 'gzip'}
        else:
            return {'Body': io.BytesIO(file.read())}

class TestDistricts (unittest.TestCase):

    def test_Partial_from_event(self):
        ''' Partial.from_event() creates the right properties with geometry key.
        '''
        storage = unittest.mock.Mock()
        storage.s3.get_object.return_value = {'Body': io.BytesIO(b'POINT (0.00001 0.00001)')}

        partial = districts.Partial.from_event(dict(index=-1, geometry_key='uploads/0/districts/0.wkt',
            upload={'id': 'ID', 'key': 'uploads/ID/upload/file.geojson'}, compactness={}), storage)
        self.assertEqual(str(partial.geometry), 'POINT (0.00001 0.00001)')
        self.assertEqual(partial.index, -1)
        self.assertEqual(partial.totals, {})
        self.assertEqual(partial.compactness, {})
        self.assertEqual(partial.precincts, [])
        self.assertEqual(partial.tiles, ['12/2048/2047'])
        self.assertEqual(partial.upload.id, 'ID')
    
    def test_Partial_contains_tile(self):
        ''' Partial.contains_tile() returns correct values.
        '''
        # District partial within the western hemisphere, touching the prime meridian
        partial = districts.Partial(0, {}, None, None, None, None, None,
            ogr.CreateGeometryFromWkt('POLYGON ((0 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,0 -0.0004693,0 0,0 0.0004532))'))
        
        self.assertTrue(partial.contains_tile('20/524287/524287'),
            'Tiny tile should be contained entirely inside district')
        
        self.assertFalse(partial.contains_tile('20/524288/524287'),
            'Tiny tile should touch eastern boundary of district')
        
        self.assertFalse(partial.contains_tile('12/2047/2048'),
            'Large tile overlaps district')
    
    def test_Partial_tile_geometry(self):
        ''' Partial.tile_geometry() returns correct geometries.
        '''
        # District partial within the western hemisphere, touching the prime meridian
        partial = districts.Partial(0, {}, None, None, None, None, None,
            ogr.CreateGeometryFromWkt('POLYGON ((0 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,0 -0.0004693,0 0,0 0.0004532))'))
        
        g1 = partial.tile_geometry('12/2047/2047')
        g2 = partial.tile_geometry('12/2047/2048')
        g3 = g1.Union(g2)
        
        self.assertAlmostEqual(g3.Area(), partial.geometry.Area(), 9,
            'Two larger tiles should pretty much cover district completely')
        
        g4 = partial.tile_geometry('20/524287/524287')
        
        self.assertTrue(g4.Within(partial.geometry),
            'Tiny tile should be contained entirely inside district')
        
        g5 = partial.tile_geometry('20/524288/524287')
        
        self.assertEqual(g5.Area(), 0, 'Tiny tile should just be a line')
        self.assertTrue(g5.Touches(partial.geometry),
            'Tiny tile should touch eastern boundary of district')
        
        g6 = partial.tile_geometry('20/524289/524287')
        
        self.assertEqual(g6.Area(), 0, 'Tiny tile should be completely empty')
        self.assertTrue(g6.Disjoint(partial.geometry),
            'Tiny tile should touch no part of district')
    
    def test_Partial_to_event(self):
        ''' Partial.to_event() and .from_event() work together.
        '''
        polygon_wkt = 'POLYGON ((-0.0002360 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,-0.0000268 -0.0004693,-0.0000187 -0.0000214,-0.0002360 0.0004532))'
        
        storage = unittest.mock.Mock()
        storage.s3.get_object.return_value = {'Body': io.BytesIO(polygon_wkt.encode('utf8'))}

        partial1 = districts.Partial(0, {}, {'Reock': -1},
            [{"type": "Feature", "properties": {"GEOID": "3", "NAME": "Precinct 3", "Voters": 4, "Red Votes": 3, "Blue Votes": 0, "PlanScore:Fraction": 0.563558429345361}, "geometry": {"type": "Polygon", "coordinates": [[[-0.0003853, 0.0], [-0.0003819, 2.5e-06], [-0.0003824, 1.16e-05], [-0.0003895, 1.16e-05], [-0.000391, 1.47e-05], [-0.0003922, 2.1e-05], [-0.0003832, 3.27e-05], [-0.0003844, 3.81e-05], [-0.0003751, 5.2e-05], [-0.0003683, 5.48e-05], [-0.0003685, 5.99e-05], [-0.0003642, 6.45e-05], [-0.0003597, 6.45e-05], [-0.0003531, 6.45e-05], [-0.0003432, 6.91e-05], [-0.0003379, 6.96e-05], [-0.0003321, 7.06e-05], [-0.0003273, 7.72e-05], [-0.0003268, 8.46e-05], [-0.0003185, 8.97e-05], [-0.0003109, 9.04e-05], [-0.0003064, 9.5e-05], [-0.0002973, 9.45e-05], [-0.0002978, 0.0001047], [-0.0002887, 0.0001103], [-0.0002826, 0.0001067], [-0.0002746, 0.0001042], [-0.0002756, 0.0001164], [-0.0002852, 0.0001179], [-0.0002852, 0.0001245], [-0.0002776, 0.0001291], [-0.0002776, 0.0001438], [-0.0002756, 0.0001464], [-0.00027, 0.0001474], [-0.0002644, 0.0001606], [-0.0002619, 0.0001657], [-0.0002518, 0.0001632], [-0.0002463, 0.0001738], [-0.0002397, 0.0001728], [-0.0002286, 0.0001815], [-0.0002225, 0.0001815], [-0.0002205, 0.0001922], [-0.0002154, 0.0001947], [-0.0002114, 0.0002049], [-0.0001973, 0.0002166], [-0.0001952, 0.0002237], [-0.0001811, 0.0002181], [-0.0001821, 0.000213], [-0.0001882, 0.0002038], [-0.0001856, 0.0001988], [-0.0001856, 0.0001942], [-0.0001882, 0.000184], [-0.0001826, 0.000184], [-0.000176, 0.0001749], [-0.0001715, 0.0001754], [-0.0001634, 0.0001866], [-0.0001594, 0.0001876], [-0.0001538, 0.0001916], [-0.0001478, 0.0001855], [-0.0001382, 0.0001922], [-0.0001255, 0.0001906], [-0.000125, 0.000183], [-0.000118, 0.0001825], [-0.0001175, 0.0001898], [-3.16e-05, 0.0], [-0.0003853, 0.0]]]}}],
            ["whatever"], None, data.Upload('ID', 'key.json'),
            ogr.CreateGeometryFromWkt(polygon_wkt))
        
        partial2 = districts.Partial.from_event(partial1.to_event(), storage)
        
        self.assertEqual(partial2.index, partial1.index)
        self.assertEqual(partial2.precincts[0], partial1.precincts[0])
        self.assertEqual(partial2.compactness['Reock'], partial1.compactness['Reock'])
        self.assertEqual(partial2.tiles, partial1.tiles)
        self.assertEqual(str(partial2.geometry_key), str(partial1.geometry_key))
    
    def test_Partial_scrunching(self):
        ''' Partial.scrunch() and .unscrunch() work symmetrically.
        '''
        for value in [None, 0, False, True, 'Yo']:
            self.assertEqual(districts.Partial.unscrunch(districts.Partial.scrunch(value)),
                value, 'Simple scalar values should unscrunch cleanly')

        for value in [['Yo'], {'Yo': 'Yo'}]:
            self.assertEqual(districts.Partial.unscrunch(districts.Partial.scrunch(value)),
                value, 'Lists and dictionaries should unscrunch cleanly')
            self.assertEqual(districts.Partial.unscrunch(value), value,
                'Lists and dictionaries should unscrunch to themselves')
    
    def test_tile_geometry(self):
        ''' Correct tile geometries are returned from tile_geometry().
        '''
        w1, e1, s1, n1 = districts.tile_geometry('0/0/0').GetEnvelope()
        self.assertAlmostEqual(w1, -180, 9)
        self.assertAlmostEqual(e1,  180, 9)
        self.assertAlmostEqual(s1, -85.051128780, 9)
        self.assertAlmostEqual(n1,  85.051128780, 9)

        w2, e2, s2, n2 = districts.tile_geometry('12/656/1582').GetEnvelope()
        self.assertAlmostEqual(w2, -122.34375, 9)
        self.assertAlmostEqual(e2, -122.255859375, 9)
        self.assertAlmostEqual(s2, 37.788081384120, 9)
        self.assertAlmostEqual(n2, 37.857507156252, 9)

    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('boto3.client')
    @unittest.mock.patch('planscore.compactness.get_scores')
    @unittest.mock.patch('planscore.districts.post_score_results')
    @unittest.mock.patch('planscore.districts.consume_tiles')
    @unittest.mock.patch('planscore.util.add_sqs_logging_handler')
    def test_lambda_handler_init(self, add_sqs_logging_handler, consume_tiles,
        post_score_results, get_scores, boto3_client, stdout):
        ''' Lambda event data with just geometry starts the process.
        '''
        s3 = boto3_client.return_value
        s3.get_object.return_value = {'Body': io.BytesIO(b'POLYGON ((-0.0002360 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,-0.0000268 -0.0004693,-0.0000187 -0.0000214,-0.0002360 0.0004532))')}
        
        get_scores.return_value = {'Reock': -1}

        event = {'index': -1, 'bucket': 'bucket-name',
            'upload': {'id': 'ID', 'key': 'uploads/ID/upload/file.geojson'},
            'geometry_key': 'geom.wkt'}

        districts.lambda_handler(event, None)
        storage, partial = consume_tiles.mock_calls[0][1]
        self.assertEqual((partial.index, partial.totals, partial.precincts, partial.tiles, partial.upload.id),
            (-1, {}, [], ['12/2047/2047', '12/2047/2048'], 'ID'))
        self.assertEqual(len(boto3_client.return_value.invoke.mock_calls), 0)
        post_score_results.assert_called_once_with(storage, partial)

        get_scores.assert_called_once_with(partial.geometry)
        self.assertEqual(partial.compactness, get_scores.return_value)

    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('boto3.client')
    @unittest.mock.patch('planscore.compactness.get_scores')
    @unittest.mock.patch('planscore.districts.post_score_results')
    @unittest.mock.patch('planscore.districts.consume_tiles')
    @unittest.mock.patch('planscore.util.add_sqs_logging_handler')
    def test_lambda_handler_timeout(self, add_sqs_logging_handler, consume_tiles,
        post_score_results, get_scores, boto3_client, stdout):
        ''' Lambda event hands off the process when no time is left.
        '''
        s3 = boto3_client.return_value
        s3.get_object.return_value = {'Body': io.BytesIO(b'POLYGON ((-0.0002360 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,-0.0000268 -0.0004693,-0.0000187 -0.0000214,-0.0002360 0.0004532))')}

        event = {'index': -1, 'bucket': 'bucket-name', 'prefix': 'data/XX',
            'upload': {'id': 'ID', 'key': 'uploads/ID/upload/file.geojson'},
            'geometry_key': 'geom.wkt'}

        context = unittest.mock.Mock()
        context.get_remaining_time_in_millis.return_value = 0
        consume_tiles.return_value = [None]

        districts.lambda_handler(event, context)
        self.assertEqual(len(boto3_client.return_value.invoke.mock_calls), 1)

        kwargs = boto3_client.return_value.invoke.mock_calls[0][2]
        self.assertEqual(kwargs['FunctionName'], districts.FUNCTION_NAME)
        self.assertEqual(kwargs['InvocationType'], 'Event')
        self.assertIn(b'"index": -1', kwargs['Payload'])
        self.assertIn(b'"id": "ID"', kwargs['Payload'])
        self.assertIn(event['bucket'].encode('utf8'), kwargs['Payload'])
        self.assertIn(event['prefix'].encode('utf8'), kwargs['Payload'])

        self.assertEqual(len(post_score_results.mock_calls), 0)

    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('boto3.client')
    @unittest.mock.patch('planscore.compactness.get_scores')
    @unittest.mock.patch('planscore.districts.post_score_results')
    @unittest.mock.patch('planscore.districts.consume_tiles')
    @unittest.mock.patch('planscore.util.add_sqs_logging_handler')
    def test_lambda_handler_continue(self, add_sqs_logging_handler, consume_tiles,
        post_score_results, get_scores, boto3_client, stdout):
        ''' Lambda event data with existing totals continues the process.
        '''
        s3 = boto3_client.return_value
        s3.get_object.return_value = {'Body': io.BytesIO(b'POLYGON ((-0.0002360 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,-0.0000268 -0.0004693,-0.0000187 -0.0000214,-0.0002360 0.0004532))')}

        event = {'index': -1, 'bucket': 'bucket-name', 'totals': {},
            'precincts': [{'Totals': 1}], 'tiles': ['12/2047/2048'],
            'upload': {'id': 'ID', 'key': 'uploads/ID/upload/file.geojson'},
            'geometry_key': 'geom.wkt', 'compactness': {'Reock': -1}}

        districts.lambda_handler(event, None)
        storage, partial = consume_tiles.mock_calls[0][1]
        self.assertEqual((partial.index, partial.totals, partial.precincts, partial.tiles, partial.upload.id),
            (-1, {}, [{'Totals': 1}], ['12/2047/2048'], 'ID'))
        self.assertEqual(len(boto3_client.return_value.invoke.mock_calls), 0)
        post_score_results.assert_called_once_with(storage, partial)
        
        self.assertEqual(len(get_scores.mock_calls), 0,
            'Should not calculate compactness scores if they are provided')

    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('boto3.client')
    @unittest.mock.patch('planscore.compactness.get_scores')
    @unittest.mock.patch('planscore.districts.post_score_results')
    @unittest.mock.patch('planscore.districts.consume_tiles')
    @unittest.mock.patch('planscore.util.add_sqs_logging_handler')
    def test_lambda_handler_final(self, add_sqs_logging_handler, consume_tiles,
        post_score_results, get_scores, boto3_client, stdout):
        ''' Lambda event for the final district does not hand off to the score function.
        '''
        s3 = boto3_client.return_value
        s3.get_object.return_value = {'Body': io.BytesIO(b'POLYGON ((-0.0002360 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,-0.0000268 -0.0004693,-0.0000187 -0.0000214,-0.0002360 0.0004532))')}

        event = {'index': -1, 'bucket': 'bucket-name',
            'upload': {'id': 'ID', 'key': 'uploads/ID/upload/file.geojson'},
            'geometry_key': 'geom.wkt'}

        districts.lambda_handler(event, None)
        storage, partial = consume_tiles.mock_calls[0][1]
        self.assertEqual((partial.index, partial.totals, partial.precincts, partial.tiles, partial.upload.id),
            (-1, {}, [], ['12/2047/2047', '12/2047/2048'], 'ID'))
        post_score_results.assert_called_once_with(storage, partial)

    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('boto3.client')
    @unittest.mock.patch('planscore.compactness.get_scores')
    @unittest.mock.patch('planscore.districts.consume_tiles')
    @unittest.mock.patch('planscore.util.add_sqs_logging_handler')
    def test_lambda_handler_overdue(self, add_sqs_logging_handler, consume_tiles,
        get_scores, boto3_client, stdout):
        ''' Lambda event for an overdue upload errors out.
        '''
        s3 = boto3_client.return_value
        s3.get_object.return_value = {'Body': io.BytesIO(b'POLYGON ((-0.0002360 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,-0.0000268 -0.0004693,-0.0000187 -0.0000214,-0.0002360 0.0004532))')}

        event = {'index': -1, 'bucket': 'bucket-name', 'prefix': 'data/XX',
            'upload': {'id': 'ID', 'key': 'uploads/ID/upload/file.geojson', 'start_time': 1},
            'geometry_key': 'geom.wkt'}

        context = unittest.mock.Mock()
        context.get_remaining_time_in_millis.return_value = 0
        consume_tiles.return_value = [None]

        with self.assertRaises(RuntimeError):
            districts.lambda_handler(event, context)

    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('time.time')
    def test_post_score_results(self, time_time, stdout):
        ''' Expected results are posted to S3.
        '''
        time_time.return_value = -1
        
        storage = data.Storage(unittest.mock.Mock(), 'bucket-name', 'data/XX')
        partial = districts.Partial(-1, {"Voters": 1}, {}, [], [], 'uploads/ID/geometries/-1.wkt',
            data.Upload('ID', 'uploads/ID/upload/file.geojson', districts=[None, None]), None)
        
        districts.post_score_results(storage, partial)

        storage.s3.put_object.assert_called_once_with(
            ACL='bucket-owner-full-control', Body=b'{\n  "index": -1,\n  "totals": {\n    "Voters": 1\n  },\n  "compactness": {},\n  "precincts": 0,\n  "tiles": [],\n  "upload": {\n    "id": "ID",\n    "key": "uploads/ID/upload/file.geojson",\n    "model": null,\n    "districts": [\n      null,\n      null\n    ],\n    "summary": {},\n    "progress": null,\n    "start_time": -1,\n    "message": null\n  }\n}',
            Bucket='bucket-name', ContentType='text/json', Key='uploads/ID/districts/-1.json')
    @unittest.mock.patch('planscore.districts.get_tile_metadata')
    @unittest.mock.patch('planscore.districts.load_tile_precincts')
    @unittest.mock.patch('planscore.districts.score_precinct')
    def test_consume_tiles(self, score_precinct, load_tile_precincts, get_tile_metadata):
        ''' Expected updates are made to totals dictionary.
        '''
        cases = [
            ({'Voters': 0}, [], [({'Voters': 1}, {'Voters': 2}), ({'Voters': 4}, {'Voters': 8})]),
            ({'Voters': 0}, [{'Voters': 1}, {'Voters': 2}], [({'Voters': 4}, {'Voters': 8})]),
            ({'Voters': 0}, [{'Voters': 1}, {'Voters': 2}, {'Voters': 4}, {'Voters': 8}], []),
            ({'Voters': 3}, [{'Voters': 4}, {'Voters': 8}], []),
            ({'Voters': 15}, [], []),
            ]
        
        def mock_score_precinct(partial, precinct, tile_zxy):
            partial.totals['Voters'] += precinct['Voters']
        
        storage = unittest.mock.Mock()
        storage.prefix = 'XX/0001'
        
        # Just use the identity function to extend precincts
        load_tile_precincts.side_effect = lambda storage, tile: tile
        score_precinct.side_effect = mock_score_precinct
        
        for (index, (totals, precincts, tiles)) in enumerate(cases):
            upload = data.Upload('ID', 'uploads/ID/upload/file.zip')
            partial = districts.Partial(-1, totals, None, precincts, tiles, None, upload, None)
            iterations = list(districts.consume_tiles(storage, partial))
            self.assertFalse(partial.precincts, 'Precincts should be completely emptied ({})'.format(index))
            self.assertFalse(partial.tiles, 'Tiles should be completely emptied ({})'.format(index))
            self.assertEqual(partial.totals['Voters'], 15, '({})'.format(index))
            self.assertEqual(partial.index, -1)
        
        self.assertEqual(len(score_precinct.mock_calls), 14)
    
    @unittest.mock.patch('planscore.districts.get_tile_metadata')
    @unittest.mock.patch('planscore.districts.load_tile_precincts')
    @unittest.mock.patch('planscore.districts.score_precinct')
    def test_consume_tiles_detail(self, score_precinct, load_tile_precincts, get_tile_metadata):
        ''' Expected updates are made to totals dictionary and lists.
        '''
        def mock_score_precinct(partial, precinct, tile_zxy):
            partial.totals['Voters'] += precinct['Voters']
        
        storage = unittest.mock.Mock()
        storage.prefix = 'XX/0001'
        
        # Just use the identity function to extend precincts
        load_tile_precincts.side_effect = lambda storage, tile: tile
        score_precinct.side_effect = mock_score_precinct

        totals, precincts, tiles = {'Voters': 0}, [{'Voters': 1}], \
            [({'Voters': 2}, ), ({'Voters': 4}, {'Voters': 8})]
        
        upload = data.Upload('ID', None)
        partial = districts.Partial(-1, totals, None, precincts, tiles, None, upload, None)
        call = districts.consume_tiles(storage, partial)
        self.assertEqual((partial.index, partial.totals, partial.precincts, partial.tiles, partial.upload.id),
            (-1, {'Voters': 0}, [{'Voters': 1}], [({'Voters': 2}, ), ({'Voters': 4}, {'Voters': 8})], 'ID'),
            'Should see the original lists unchanged')
        
        next(call)
        self.assertEqual((partial.index, partial.totals, partial.precincts, partial.tiles, partial.upload.id),
            (-1, {'Voters': 1}, [], [({'Voters': 2}, ), ({'Voters': 4}, {'Voters': 8})], 'ID'),
            'Should see the precincts list emptied and tiles list untouched')
        
        next(call)
        self.assertEqual((partial.index, partial.totals, partial.precincts, partial.tiles, partial.upload.id),
            (-1, {'Voters': 3}, [], [({'Voters': 4}, {'Voters': 8})], 'ID'),
            'Should see the first tile scored and a still-empty precincts list')
        
        next(call)
        self.assertEqual((partial.index, partial.totals, partial.precincts, partial.tiles, partial.upload.id),
            (-1, {'Voters': 15}, [], [], 'ID'),
            'Should see the precincts and tiles lists emptied')

        with self.assertRaises(StopIteration):
            next(call)
    
    def test_score_precinct(self):
        ''' Correct values appears in totals dict after scoring a precinct.
        '''
        totals = {"Voters": 0, "Red Votes": 0, "REP999": 0, "Blue Votes": 0, "DEM999": 0}
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-0.0002360 0.0004532,-0.0006812 0.0002467,-0.0006356 -0.0003486,-0.0000268 -0.0004693,-0.0000187 -0.0000214,-0.0002360 0.0004532))')
        precinct = {"type": "Feature", "properties": {"GEOID": "3", "NAME": "Precinct 3", "Voters": 4, "Red Votes": 3, "REP999": 3, "Blue Votes": 0, "DEM999": 0, "PlanScore:Fraction": 0.563558429345361}, "geometry": {"type": "Polygon", "coordinates": [[[-0.0003853, 0.0], [-0.0003819, 2.5e-06], [-0.0003824, 1.16e-05], [-0.0003895, 1.16e-05], [-0.000391, 1.47e-05], [-0.0003922, 2.1e-05], [-0.0003832, 3.27e-05], [-0.0003844, 3.81e-05], [-0.0003751, 5.2e-05], [-0.0003683, 5.48e-05], [-0.0003685, 5.99e-05], [-0.0003642, 6.45e-05], [-0.0003597, 6.45e-05], [-0.0003531, 6.45e-05], [-0.0003432, 6.91e-05], [-0.0003379, 6.96e-05], [-0.0003321, 7.06e-05], [-0.0003273, 7.72e-05], [-0.0003268, 8.46e-05], [-0.0003185, 8.97e-05], [-0.0003109, 9.04e-05], [-0.0003064, 9.5e-05], [-0.0002973, 9.45e-05], [-0.0002978, 0.0001047], [-0.0002887, 0.0001103], [-0.0002826, 0.0001067], [-0.0002746, 0.0001042], [-0.0002756, 0.0001164], [-0.0002852, 0.0001179], [-0.0002852, 0.0001245], [-0.0002776, 0.0001291], [-0.0002776, 0.0001438], [-0.0002756, 0.0001464], [-0.00027, 0.0001474], [-0.0002644, 0.0001606], [-0.0002619, 0.0001657], [-0.0002518, 0.0001632], [-0.0002463, 0.0001738], [-0.0002397, 0.0001728], [-0.0002286, 0.0001815], [-0.0002225, 0.0001815], [-0.0002205, 0.0001922], [-0.0002154, 0.0001947], [-0.0002114, 0.0002049], [-0.0001973, 0.0002166], [-0.0001952, 0.0002237], [-0.0001811, 0.0002181], [-0.0001821, 0.000213], [-0.0001882, 0.0002038], [-0.0001856, 0.0001988], [-0.0001856, 0.0001942], [-0.0001882, 0.000184], [-0.0001826, 0.000184], [-0.000176, 0.0001749], [-0.0001715, 0.0001754], [-0.0001634, 0.0001866], [-0.0001594, 0.0001876], [-0.0001538, 0.0001916], [-0.0001478, 0.0001855], [-0.0001382, 0.0001922], [-0.0001255, 0.0001906], [-0.000125, 0.000183], [-0.000118, 0.0001825], [-0.0001175, 0.0001898], [-3.16e-05, 0.0], [-0.0003853, 0.0]]]}}
        partial = districts.Partial(None, totals, None, None, None, None, None, geometry)
        
        # Check each overlapping tile
        for tile_zxy in ('12/2047/2047', '12/2047/2048', '12/2048/2047', '12/2048/2048'):
            districts.score_precinct(partial, precinct, tile_zxy)
        
        self.assertAlmostEqual(partial.totals['Voters'], 2.25423371, places=2)
        self.assertAlmostEqual(partial.totals['Red Votes'], 1.69067528, places=2)
        self.assertAlmostEqual(partial.totals['REP999'], 1.69067528, places=2)
        self.assertAlmostEqual(partial.totals['Blue Votes'], 0, places=2)
        self.assertAlmostEqual(partial.totals['DEM999'], 0, places=2)
    
    # Precinct and Census block (represented as points) score cases:
    #
    # 1. precinct from tile within district - 100%
    # 2. tile overlapping district:
    #   2a. precinct within district - 100%
    #   2b. precinct overlaps district - ?%
    #   2c. precinct touches district - 0%
    #   2d. precinct outside district - 0%
    #   2e. block-point within district - 100%
    #   2f. block-point outside district - 0%
    # 3. precinct from tile touching district - 0%
    # 4. precinct from tile outside district - 0%
    # 5. block-point from tile within district - 100%
    # 6. block-point from tile outside district - 0%
    # 7. empty geometry from tile within district - 0%
    
    def test_score_precinct_1_tile_within(self):
        ''' Correct voter count for a precinct from tile within district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,1 1,1 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertTrue(partial.contains_tile('12/2048/2047'))

        precinct = {"type": "Feature", "properties": {"Voters": 1, "PlanScore:Fraction": 0.5}, "geometry": {"type": "Polygon", "coordinates": [[[.02, .02], [.02, .06], [.06, .06], [.06, .02], [.02, .02]]]}}
        districts.score_precinct(partial, precinct, '12/2048/2047')
        self.assertAlmostEqual(partial.totals['Voters'], .5, 9)
    
    def test_score_precinct_2a_tile_overlaps_precinct_within(self):
        ''' Correct voter count for a precinct within district from tile overlapping district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,0.17 1,0.17 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2049/2046'))

        precinct = {"type": "Feature", "properties": {"Voters": 1, "PlanScore:Fraction": 0.5}, "geometry": {"type": "Polygon", "coordinates": [[[.12, .12], [.12, .16], [.16, .16], [.16, .12], [.12, .12]]]}}
        districts.score_precinct(partial, precinct, '12/2049/2046')
        self.assertAlmostEqual(partial.totals['Voters'], .5, 9)
    
    def test_score_precinct_2b_tile_overlaps_precinct_overlaps(self):
        ''' Correct voter count for a precinct overlapping district from tile overlapping district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,0.14 1,0.14 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2049/2046'))

        precinct = {"type": "Feature", "properties": {"Voters": 1, "PlanScore:Fraction": 0.5}, "geometry": {"type": "Polygon", "coordinates": [[[.12, .12], [.12, .16], [.16, .16], [.16, .12], [.12, .12]]]}}
        districts.score_precinct(partial, precinct, '12/2049/2046')
        self.assertAlmostEqual(partial.totals['Voters'], .25, 9)
    
    def test_score_precinct_2c_tile_overlaps_precinct_touches(self):
        ''' Correct voter count for a precinct touching district from tile overlapping district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,0.12 1,0.12 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2049/2046'))

        precinct = {"type": "Feature", "properties": {"Voters": 1, "PlanScore:Fraction": 0.5}, "geometry": {"type": "Polygon", "coordinates": [[[.12, .12], [.12, .16], [.16, .16], [.16, .12], [.12, .12]]]}}
        districts.score_precinct(partial, precinct, '12/2049/2046')
        self.assertAlmostEqual(partial.totals['Voters'], 0., 9)
    
    def test_score_precinct_2d_tile_overlaps_precinct_outside(self):
        ''' Correct voter count for a precinct outside district from tile overlapping district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,0.11 1,0.11 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2049/2046'))

        precinct = {"type": "Feature", "properties": {"Voters": 1, "PlanScore:Fraction": 0.5}, "geometry": {"type": "Polygon", "coordinates": [[[.12, .12], [.12, .16], [.16, .16], [.16, .12], [.12, .12]]]}}
        districts.score_precinct(partial, precinct, '12/2049/2046')
        self.assertAlmostEqual(partial.totals['Voters'], 0., 9)
    
    def test_score_precinct_2e_tile_overlaps_blockpoint_within(self):
        ''' Correct voter count for a block-point within district from tile overlapping district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,0.17 1,0.17 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2049/2046'))

        blockpoint = {"type": "Feature", "properties": {"Voters": 1}, "geometry": {"type": "Point", "coordinates": [.14, .14]}}
        districts.score_precinct(partial, blockpoint, '12/2049/2046')
        self.assertAlmostEqual(partial.totals['Voters'], 1, 9)
    
    def test_score_precinct_2f_tile_overlaps_blockpoint_outside(self):
        ''' Correct voter count for a block-point outside district from tile overlapping district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,0.11 1,0.11 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2049/2046'))

        blockpoint = {"type": "Feature", "properties": {"Voters": 1}, "geometry": {"type": "Point", "coordinates": [.14, .14]}}
        districts.score_precinct(partial, blockpoint, '12/2049/2046')
        self.assertAlmostEqual(partial.totals['Voters'], 0., 9)
    
    def test_score_precinct_3_tile_touches(self):
        ''' Correct voter count for a precinct from tile touching district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,0.087890625 1,0.087890625 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2049/2046'))

        precinct = {"type": "Feature", "properties": {"Voters": 1, "PlanScore:Fraction": 0.5}, "geometry": {"type": "Polygon", "coordinates": [[[.12, .12], [.12, .16], [.16, .16], [.16, .12], [.12, .12]]]}}
        districts.score_precinct(partial, precinct, '12/2049/2046')
        self.assertAlmostEqual(partial.totals['Voters'], 0., 9)
    
    def test_score_precinct_4_tile_outside(self):
        ''' Correct voter count for a precinct from tile outside district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,1 1,1 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2059/2047'))

        precinct = {"type": "Feature", "properties": {"Voters": 1, "PlanScore:Fraction": 0.5}, "geometry": {"type": "Polygon", "coordinates": [[[.02, .02], [.02, .06], [.06, .06], [.06, .02], [.02, .02]]]}}
        districts.score_precinct(partial, precinct, '12/2059/2047')
        self.assertAlmostEqual(partial.totals['Voters'], 0., 9)
    
    def test_score_precinct_5_blockpoint_within(self):
        ''' Correct voter count for a block-point from tile within district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,1 1,1 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertTrue(partial.contains_tile('12/2048/2047'))

        blockpoint = {"type": "Feature", "properties": {"Voters": 1}, "geometry": {"type": "Point", "coordinates": [.04, .04]}}
        districts.score_precinct(partial, blockpoint, '12/2048/2047')
        self.assertAlmostEqual(partial.totals['Voters'], 1, 9)
    
    def test_score_precinct_6_blockpoint_outside(self):
        ''' Correct voter count for a block-point from tile outside district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,1 1,1 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertFalse(partial.contains_tile('12/2059/2047'))

        blockpoint = {"type": "Feature", "properties": {"Voters": 1}, "geometry": {"type": "Point", "coordinates": [1.00, 0.05]}}
        districts.score_precinct(partial, blockpoint, '12/2059/2047')
        self.assertAlmostEqual(partial.totals['Voters'], 0., 9)
    
    def test_score_precinct_7_empty(self):
        ''' Correct voter count for an empty geometry from tile within district.
        '''
        geometry = ogr.CreateGeometryFromWkt('POLYGON ((-1 -1,-1 1,1 1,1 -1,-1 -1))')
        partial = districts.Partial(None, {'Voters': 0}, None, None, None, None, None, geometry)
        self.assertTrue(partial.contains_tile('12/2048/2047'))

        empty = {"type": "Feature", "properties": {"Voters": 1}, "geometry": {"type": "GeometryCollection", "geometries": [ ]}}
        districts.score_precinct(partial, empty, '12/2048/2047')
        self.assertAlmostEqual(partial.totals['Voters'], 0., 9)
    
    @unittest.mock.patch('planscore.districts.load_tile_precincts')
    def test_iterate_precincts(self, load_tile_precincts):
        ''' Expected list of precincts comes back from a pair of lists.
        '''
        cases = [
            ([],        [],                 []),
            ([1, 2],    [],                 [1, 2]),
            ([1, 2],    [(3, 4)],           [1, 2, 3, 4]),
            ([1, 2],    [(3, 4), (5, 6)],   [1, 2, 3, 4, 5, 6]),
            ([],        [(3, 4), (5, 6)],   [3, 4, 5, 6]),
            ([],        [(5, 6)],           [5, 6]),
            ]
        
        # Just use the identity function to extend precincts
        load_tile_precincts.side_effect = lambda storage, tile: tile
        expected_calls = 0
        
        for (input, tiles, expected) in cases:
            expected_calls += len(tiles)
            actual = list(districts.iterate_precincts(None, input, tiles))
            self.assertFalse(input, 'Input should be completely emptied')
            self.assertFalse(tiles, 'Tiles should be completely emptied')
            self.assertEqual(actual, expected)
        
        self.assertEqual(len(load_tile_precincts.mock_calls), expected_calls)
    
    def test_get_tile_metadata(self):
        '''
        '''
        s3 = unittest.mock.Mock()
        storage = data.Storage(s3, 'bucket-name', 'XX')

        s3.head_object.return_value = {'ContentLength': -1}
        metadata1 = districts.get_tile_metadata(storage, '12/-1/-1')
        self.assertEqual(metadata1['size'], -1)

        s3.head_object.return_value = {'SomethingElse': -1}
        metadata2 = districts.get_tile_metadata(storage, '12/-1/-1')
        self.assertIsNone(metadata2['size'])
    
    def test_load_tile_precincts(self):
        '''
        '''
        s3 = unittest.mock.Mock()
        s3.get_object.side_effect = mock_s3_get_object
        storage = data.Storage(s3, 'bucket-name', 'XX')

        precincts1 = districts.load_tile_precincts(storage, '12/2047/2047')
        s3.get_object.assert_called_once_with(Bucket='bucket-name', Key='XX/12/2047/2047.geojson')
        self.assertEqual(len(precincts1), 4)

        precincts2 = districts.load_tile_precincts(storage, '12/-1/-1')
        self.assertEqual(len(precincts2), 0)

    @unittest.mock.patch('sys.stdout')
    def test_get_geometry_tile_zxys(self, stdout):
        ''' Get an expected list of Z/X/Y tile strings for a geometry.
        '''
        with open(os.path.join(os.path.dirname(__file__), 'data', 'null-plan.geojson')) as file:
            geojson = json.load(file)
        
        feature1, feature2 = geojson['features']

        geometry1 = ogr.CreateGeometryFromJson(json.dumps(feature1['geometry']))
        done1 = districts.get_geometry_tile_zxys(geometry1)

        geometry2 = ogr.CreateGeometryFromJson(json.dumps(feature2['geometry']))
        done2 = districts.get_geometry_tile_zxys(geometry2)
        
        self.assertEqual(done1, ['12/2047/2047', '12/2047/2048'])
        self.assertEqual(done2, ['12/2047/2047', '12/2048/2047', '12/2047/2048', '12/2048/2048'])
