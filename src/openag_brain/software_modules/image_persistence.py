#!/usr/bin/env python
"""
The `image_persistence.py` module listens for image data from an environment,
converts the images to PNG format and stores them in the CouchDB instance as
attachments to environmental data points. There should be example one instance
of this module for every environment in the system that has camera(s) connected
to it.

It assumes all topics of the type `sensor_msgs/Image` under the namespace
for the environment are streams of images from connected webcams.
"""
import time
import rospy
import requests
from PIL import Image
from couchdb import Server
from StringIO import StringIO
from sensor_msgs.msg import Image as ImageMsg

from openag.cli.config import config as cli_config
from openag.models import EnvironmentalDataPoint, SoftwareModule
from openag.db_names import ENVIRONMENTAL_DATA_POINT, SOFTWARE_MODULE
from openag.var_types import AERIAL_IMAGE

from openag_brain import params

class ImagePersistence:
    image_format_mapping = {
        "rgb8": "RGB",
        "rgba8": "RGBA"
    }

    def __init__(self, db, topic, variable, environment, min_update_interval):
        self.db = db
        self.variable = variable
        self.environment = environment
        self.min_update_interval = min_update_interval
        self.last_update = 0
        self.sub = rospy.Subscriber(topic, ImageMsg, self.on_image)

    def on_image(self, item):
        # Rate limit
        curr_time = time.time()
        if (curr_time - self.last_update) < self.min_update_interval:
            return
        self.last_update = curr_time

        rospy.loginfo("Posting image")

        image_format = self.image_format_mapping.get(item.encoding, None)
        if image_format is None:
            raise ValueError()
        img = Image.fromstring(
            image_format, (item.width, item.height), item.data
        )
        point = EnvironmentalDataPoint({
            "environment": self.environment,
            "variable": self.variable.name,
            "is_desired": False,
            "value": None,
            "timestamp": time.time()
        })
        point_id, point_rev = self.db.save(point)
        url = "{db_url}/{point_id}/image?rev={rev}".format(
            db_url=self.db.resource.url, point_id=point_id, rev=point_rev
        )
        buf = StringIO()
        img.save(buf, "PNG")
        buf.seek(0)
        headers = {
            "Content-Type": "image/png"
        }
        res = requests.put(url, data=buf, headers=headers)
        if res.status_code != 201:
            raise RuntimeError(
                "Failed to post image to database: {}".format(res.content)
            )

if __name__ == '__main__':
    db_server = cli_config["local_server"]["url"]
    if not db_server:
        raise RuntimeError("No database server specified")
    server = Server(db_server)
    rospy.init_node('image_persistence_1')
    try:
        min_update_interval = rospy.get_param("~min_update_interval")
    except KeyError:
        rospy.logwarn(
            "No minimum update interval specified for image persistence module"
        )
        min_update_interval = 3600
    env_var_db = server[ENVIRONMENTAL_DATA_POINT]
    module_db = server[SOFTWARE_MODULE]
    modules = {
        module_id: SoftwareModule(module_db[module_id]) for module_id in
        module_db if not module_id.startswith("_")
    }
    persistence_objs = []
    for module_id, module_info in modules.items():
        if module_info.get("namespace", None) == "cameras":
            topic = "/cameras/{}/image_raw".format(module_id)
            persistence_objs.append(ImagePersistence(
                db=env_var_db, topic=topic, variable=AERIAL_IMAGE,
                environment=module_info["environment"],
                min_update_interval=min_update_interval
            ))
    rospy.spin()
