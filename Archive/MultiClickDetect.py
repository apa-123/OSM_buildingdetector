import cv2
import numpy as np
import geolocation
import backend
import math
import os
from .algorithms import FloodFill, Polygonify

class MultiClickDetect:
    def __init__(self, image, lat, long, zoom, threshold, first):
        # checks to see if we should be using a past flood fill
        self.first = first
        if self.first:
            self.image = image
        else:
            self.image = cv2.imread('detectors/runtime_images/flood_fill_multi_click.png')
        self.lat = lat
        self.long = long
        self.zoom = zoom
        self.THRESHOLD = threshold

    def detect_building(self):
        # Get the x_click,y coordinates of the click
        x_click, y_click = geolocation.deg_to_tilexy_matrix(self.lat, self.long, self.zoom)
        # find xtile, ytile
        xtile, ytile = geolocation.deg_to_tile(self.lat, self.long, self.zoom)

        if self.first:
            # writes the pre_image before any changes
            cv2.imwrite('detectors/runtime_images/pre_image.png', self.image)
            print("running flood fill on existing image")

        flood_fill = FloodFill(self.image, x_click, y_click, self.THRESHOLD)
        flood_fill_image, message = flood_fill.flood_fill()
        cv2.imwrite('detectors/runtime_images/flood_fill_multi_click.png', flood_fill_image)
        print("ran flood fill")

        cropped_image = flood_fill.crop_image()
        cv2.imwrite('detectors/runtime_images/flood_fill_display.png', cropped_image)
        print('cropped image')

        edge_image, total_edge_list = flood_fill.find_edges()
        cv2.imwrite('detectors/runtime_images/flood_fill_edges.png', edge_image)
        print('found edges')

        polygon = Polygonify(total_edge_list)
        rect_points = polygon.find_polygon(rectangle=True)

        vertex_list = []
        # gets polygon's points into lat/long
        for corner in rect_points:
            next_vertex = geolocation.tilexy_to_deg_matrix(xtile, ytile, self.zoom, corner[0], corner[1])
            vertex_list.append(list(next_vertex))

        return vertex_list, message
    
