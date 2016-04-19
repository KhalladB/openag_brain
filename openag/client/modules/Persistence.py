from couchdb import Server
from .models import EnvironmentalDataPointModel

class Persistence(Module):
    desired_data = Input()
    mesaured_data = Input()

    def init(self, env_id: "The id of the environment for which to record data"):
        self.server = Server()
        self.db = get_or_create_db(ENVIRONMENTAL_DATA_POINT_DB)
        # TODO: Make sure an envinroment with this ID already exists
        self.env_id = env_id

    def on_desired_data(self, item):
        point = EnvironmentalDataPointModel(
            environment=self.env_id,
            variable=item.data_type
            is_desired=True
            value=item.value,
            timestamp=item.timestamp
        )
        point.store(self.db)

    def on_measured_data(self, item):
        point = EnvironmentalDataPointModel(
            environment=self.env_id,
            variable=item.data_type
            is_desired=False
            value=item.value,
            timestamp=item.timestamp
        )
        point.store(self.db)