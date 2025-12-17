import requests
from datamodel_code_generator import InputFileType, generate
from datamodel_code_generator import DataModelType
from pathlib import Path
import json



class Generator:
    def __init__(self, baseurl:str = "http://127.0.0.1"):
        self.baseurl = baseurl

    @property
    def apispec(self):
        url = f"{self.baseurl}/api/v1/openapi.json"
        resp = requests.get(url)
        return resp.json()


    @property
    def api_models(self):
        return self.apispec


    def get_models_json(self):
        """
        Fetches the openapispec from api and stores 
        the components.schemas object as a .json file
        locally
        """
        with open('models_json.json', 'w') as f:
            f.write(json.dumps(self.api_models, indent=4))

    
    def generate_models(self):
        input_path = Path('models_json.json')
        output_path = Path("src/acex_client/models/models.py")
        generate(
            input_=input_path,
            input_file_type=InputFileType.OpenAPI,
            output=output_path,
            output_model_type=DataModelType.PydanticV2BaseModel
        )
