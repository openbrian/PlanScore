import json, io, gzip, posixpath, functools
import osgeo.ogr, boto3, botocore.exceptions, ModestMaps.OpenStreetMap, ModestMaps.Core
from . import constants, data, util, prepare_state, score

FUNCTION_NAME = 'PlanScore-RunTile'

# Borrow some Modest Maps tile math
_mercator = ModestMaps.OpenStreetMap.Provider().projection

def load_tile_precincts(storage, tile_zxy):
    ''' Get GeoJSON features for a specific tile.
    '''
    try:
        object = storage.s3.get_object(Bucket=storage.bucket,
            Key='{}/{}.geojson'.format(storage.prefix, tile_zxy))
    except botocore.exceptions.ClientError as error:
        if error.response['Error']['Code'] == 'NoSuchKey':
            return []
        raise

    if object.get('ContentEncoding') == 'gzip':
        object['Body'] = io.BytesIO(gzip.decompress(object['Body'].read()))
    
    geojson = json.load(object['Body'])
    return geojson['features']

def get_tile_zxy(model_key_prefix, tile_key):
    '''
    '''
    tile_zxy, _ = posixpath.splitext(posixpath.relpath(tile_key, model_key_prefix))
    return tile_zxy

@functools.lru_cache(maxsize=16)
def tile_geometry(tile_zxy):
    ''' Get an OGR Geometry for a web mercator tile.
    '''
    (z, x, y) = map(int, tile_zxy.split('/'))
    coord = ModestMaps.Core.Coordinate(y, x, z)
    NW = _mercator.coordinateLocation(coord)
    SE = _mercator.coordinateLocation(coord.right().down())
    wkt = 'POLYGON(({W} {N},{W} {S},{E} {S},{E} {N},{W} {N}))'.format(
        N=NW.lat, W=NW.lon, S=SE.lat, E=SE.lon)

    return osgeo.ogr.CreateGeometryFromWkt(wkt)

def score_district(district_geom, precincts, tile_geom):
    ''' Return weighted precinct totals for a district over a tile.
    '''
    totals = {}
    
    if district_geom.Disjoint(tile_geom):
        return totals
    
    partial_district_geom = district_geom.Intersection(tile_geom)

    for precinct_feat in precincts:
        subtotals = score_precinct(partial_district_geom, precinct_feat, tile_geom)
        totals.update({name: round(value + totals.get(name, 0), constants.ROUND_COUNT)
            for (name, value) in subtotals.items()})

    return totals

def score_precinct(partial_district_geom, precinct_feat, tile_geom):
    ''' Return weighted single-district totals for a precinct feature within a tile.
        
        partial_district_geom is the intersection of district and tile geometries.
    '''
    # Initialize totals to zero
    totals = {name: 0 for name in score.FIELD_NAMES if name in precinct_feat['properties']}
    precinct_geom = osgeo.ogr.CreateGeometryFromJson(json.dumps(precinct_feat['geometry']))
    
    if precinct_geom is None or precinct_geom.IsEmpty():
        # If there's no precinct geometry here, don't bother.
        return totals
    elif partial_district_geom is None or partial_district_geom.IsEmpty():
        # If there's no district geometry here, don't bother.
        return totals
    elif precinct_geom.GetGeometryType() in (osgeo.ogr.wkbPoint,
        osgeo.ogr.wkbPoint25D, osgeo.ogr.wkbMultiPoint, osgeo.ogr.wkbMultiPoint25D):
        # Points have no area
        precinct_is_point = True
        precinct_frac = 1
    else:
        precinct_is_point = False
        precinct_frac = precinct_feat['properties'][prepare_state.FRACTION_FIELD]

    if precinct_frac == 0:
        # If there's no overlap here, don't bother.
        return totals

    if tile_geom.Within(partial_district_geom):
        # Don't laboriously calculate precinct fraction if we know it's all there.
        # This is safe because precincts are clipped on tile boundaries, so a
        # fully-contained tile necessarily means the precinct is also contained.
        precinct_fraction = precinct_frac
    elif precinct_is_point:
        # Do simple inside/outside check for points
        precinct_fraction = precinct_frac if precinct_geom.Within(partial_district_geom) else 0
    else:
        try:
            overlap_geom = precinct_geom.Intersection(partial_district_geom)
        except RuntimeError as e:
            if 'TopologyException' in str(e) and not precinct_geom.IsValid():
                # Sometimes, a precinct geometry can be invalid
                # so inflate it by a tiny amount to smooth out problems
                precinct_geom = precinct_geom.Buffer(0.0000001)
                overlap_geom = precinct_geom.Intersection(partial_district_geom)
            else:
                raise
        if precinct_geom.Area() == 0:
            # If we're about to divide by zero, don't bother.
            return totals

        overlap_area = overlap_geom.Area() / precinct_geom.Area()
        precinct_fraction = overlap_area * precinct_frac
    
    for name in totals:
        precinct_value = precinct_fraction * (precinct_feat['properties'][name] or 0)
        totals[name] = round(precinct_value, constants.ROUND_COUNT)
    
    return totals

def lambda_handler(event, context):
    '''
    '''
    s3 = boto3.client('s3', endpoint_url=constants.S3_ENDPOINT_URL)
    storage = data.Storage.from_event(event['storage'], s3)
    upload = data.Upload.from_dict(event['upload'])

    try:
        tile_zxy = get_tile_zxy(upload.model.key_prefix, event['key'])
        precincts = load_tile_precincts(storage, tile_zxy)
        tile_key = data.UPLOAD_TILES_KEY.format(id=upload.id, zxy=tile_zxy)
    
        geoms_prefix = posixpath.dirname(data.UPLOAD_GEOMETRIES_KEY).format(id=upload.id)
        response = s3.list_objects(Bucket=storage.bucket, Prefix=geoms_prefix)
        geometry_keys = [object['Key'] for object in response['Contents']]
        tile_geom = tile_geometry(tile_zxy)
    
        totals = {}
    
        for geometry_key in geometry_keys:
            object = s3.get_object(Bucket=storage.bucket, Key=geometry_key)
            district_geom = osgeo.ogr.CreateGeometryFromWkt(object['Body'].read().decode('utf8'))
            totals[geometry_key] = score_district(district_geom, precincts, tile_geom)
    except Exception as err:
        totals = str(err)

    s3.put_object(Bucket=storage.bucket, Key=tile_key,
        Body=json.dumps(dict(event, tile_key=tile_key, geoms_prefix=geoms_prefix, totals=totals, precinct_count=len(precincts))).encode('utf8'),
        ContentType='text/plain', ACL='public-read')
