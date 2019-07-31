import backend
import imagery
import os
import shutil
import geolocation
import numpy as np
import json
from detectors import Detector, Rectangle
from Mask_RCNN_Detect import Mask_RCNN_Detect
from PIL import Image
from flask import Flask, render_template, request, flash, redirect, url_for, send_from_directory, send_file

app = Flask(__name__)

imd = None
program_config = {}
osm = None
mrcnn = Mask_RCNN_Detect("weights/epoch55.h5")

# gets the directories all set up
if (os.path.isdir('runtime')):
    shutil.rmtree('runtime')
os.mkdir('runtime')
os.mkdir('runtime/images')
os.mkdir('runtime/masks')

# useful function for turning request data into usable dictionaries
def result_to_dict(result):
    info = {}
    for k, v in result.items():
        info[k.lower()] = v
    return info


@app.route('/', methods=['GET'])  # base page that loads up on start/accessing the website
def login():  # this method is called when the page starts up
    return redirect('/home/')

@app.route('/home/')
def home():
    # necessary so that if one refreshes, the way memory deletes with the drawn polygons
    global osm
    osm.clear_ways_memory()
    Detector.reset()
    return render_template('DisplayMap.html')

@app.route('/home/backendWindow/', methods=['POST', 'GET'])
def backend_window():
    if (mrcnn.image_id == 1): # no images masked yet
        return send_from_directory('default_images', 'default_window.jpeg')
    return send_from_directory('runtime/masks', 'mask_{}.png'.format(mrcnn.image_id-1))

@app.route('/home/mapclick', methods=['POST'])
def mapclick():
    global osm, mcrnn
    if request.method == 'POST':
        result = request.form
        info = result_to_dict(result)
        print(info)

        lat = float(info['lat'])
        long = float(info['long'])
        zoom = int(info['zoom'])
        complex = False
        if info['complex'] == 'true':
            complex = True
        threshold = int(info['threshold'])

        merge_mode = False
        if (info['merge_mode'] == 'true'):
            merge_mode = True

        delete_click = False
        if (info['delete_click'] == 'true'):
            delete_click = True

        json_post = {}
        possible_building_matches = osm.ways_binary_search((lat, long))

        # consider moving this to a function inside the OSM_Interactor class, and copy the Rectangle has point inside code
        if possible_building_matches != None:
            for points in possible_building_matches:
                synced_building_as_rect = Rectangle(points, to_id=False)
                if synced_building_as_rect.has_point_inside((lat, long)):
                    json_post = {"rects_to_add": [],
                                "rects_to_delete": ['INSIDEBUILDING']
                                }
                    return json.dumps(json_post)

        # find xtile, ytile
        xtile, ytile = geolocation.deg_to_tile(lat, long, zoom)

        # Get those tiles
        backend_image = np.array(imd.get_tiles_around(xtile, ytile, zoom))

        # create a rectangle from click
        # rect_data includes a tuple -> (list of rectangle references to add/draw, list of rectangle ids to remove)
        # detection = None
        # if complex:
        #     detection = Detector('complex_detect', backend_image, lat, long, zoom, threshold, merge_mode)
        # elif multi_click:
        #     detection = Detector('multi_click_detect', backend_image, lat, long, zoom, threshold, merge_mode)
        # else:
        #     detection = Detector('simple_detect', backend_image, lat, long, zoom, threshold, merge_mode)

        # rect_id, rect_points, rect_ids_to_remove, message = detection.detect_building()


        # if area too big
        # if osm.check_area(rect_points, sort=False):
        #     json_post = {"rects_to_add": [],
        #                  "rects_to_delete": []
        #                  }

        # else:
            # json_post = {"rects_to_add": [{"id": rect_id,
            #                         "points": rect_points}],
            #          "rects_to_delete": {"ids": rect_ids_to_remove}
            #                 }

        if delete_click:
            lat_delete = float(info['delete_lat'])
            long_delete = float(info['delete_long'])
            id_to_delete = mrcnn.delete_mask(lat_delete, long_delete, zoom)
            json_post = {"rects_to_add": [{"ids": [],
                                        "points": []}],
                        "rects_to_delete": {"ids": [id_to_delete]}}
            return json.dumps(json_post)

        masks, message = mrcnn.detect_building(backend_image, lat, long, zoom, to_id=True, rectanglify=True, to_fill=False)

        if message == 'rectangle':
            json_post = {"rects_to_add": [{
                                            "ids": list(masks.keys()),
                                            "points": list(masks.values())
                                        }],
                        "rects_to_delete": {"ids": []}
                                }
        return json.dumps(json_post)

@app.route('/home/deleterect', methods=['POST'])
def delete_rect():
    if request.method == 'POST':
        result = request.form
        info = result_to_dict(result)
        
        # Delete the rectangle with this ID
        rect_id = int(info['rect_id'])
        mrcnn.delete_mask(building_id=rect_id)
        # Detector.delet/e_rect(rect_id)
        
    return "Success"

@app.route('/home/uploadchanges', methods=['POST'])
def upload_changes():
    print('uploading to OSM...')
    global osm
    
    if (len(Rectangle.get_all_rects()) == 0):
        print("No Rects")
        return "0"
    
    # Create the way using the list of nodes
    changeset_comment = "Added " + str(len(building_detection_combined.get_all_rects())) + " buildings."
    ways_created = osm.way_create_multiple(building_detection_combined.get_all_rects_dictionary(), changeset_comment, {"building": "yes"})
    
    # Clear the rectangle list
    building_detection_combined.delete_all_rects()
    print('finished!')
    return str(len(ways_created))

@app.route('/home/imagery/<zoom>/<x>/<y>.png', methods=['GET'])
def imagery_request(zoom, x, y):
    fname = imd.get_tile_filename(x, y, zoom)
    if not os.path.isfile(fname):
        imd.download_tile(x, y, zoom)
    return send_file(fname, mimetype="image/png")

@app.route('/home/OSMSync', methods=['POST'])
def OSM_map_sync():
    if request.method == 'POST':
        result = request.form
        info = result_to_dict(result)

        min_long = float(info['min_long'])
        min_lat = float(info['min_lat'])
        max_long = float(info['max_long'])
        max_lat = float(info['max_lat'])

        global osm
        mappable_results = osm.sync_map(min_long, min_lat, max_long, max_lat)
        if mappable_results == None or len(mappable_results) == 0:
            json_post = {'rectsToAdd': []}
            return json.dumps(json_post)
        # note that this is in a different format as the other json_post for a map click
        # mappable_results is a list with each index a building containing tuples for the coordinates of the corners
        json_post = {"rectsToAdd": mappable_results}
        return json.dumps(json_post)

@app.route('/home/citySearch', methods=['POST'])
def citySearch():
    if request.method == 'POST':
        result = request.form
        info = result_to_dict(result)
        print('info', info)
        city_name = info['query']
        coords = backend.search_city(city_name)

        if coords != None:
            json_post = {'lat': coords[0],
                          'lng': coords[1]}
            return json.dumps(json_post)

        json_post = {'lat': '-1000'}
        return json.dumps(json_post)

def start_webapp(config):
    """Starts the Flask server."""
    app.secret_key = 'super secret key'
    # app.config['SESSION_TYPE'] = 'filesystem'
    
    # Get config variables
    
    if "imageryURL" not in config:
        print("[ERROR] Could not find imageryURL in the config file!")

    # Get the imagery URL and access key
    imagery_url = config["imageryURL"]
    access_key = ""

    if "accessKey" in config:
        access_key = config["accessKey"]

    # Create imagery downloader
    global imd
    imd = imagery.ImageryDownloader(imagery_url, access_key)
    
    global program_config
    program_config = config

    global osm
    init_info = program_config["osmUpload"]
    args = ["api", "username", "password"]
    for arg in args:
        if arg not in init_info:
            print("[ERROR] Config: osmUpload->" + arg + " not found!")
            return "BREAK"

    # initializes the class for interacting with OpenStreetMap's API
    osm = backend.OSM_Interactor(init_info["api"], init_info["username"], init_info["password"])

    app.debug = True
    app.run()
