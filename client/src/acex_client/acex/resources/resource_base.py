


class Resource:

    def __init__(
            self,
            rest_client
        ):
        self.rest = rest_client

    @property
    def ep(self):
        """
        Each resource that inherits this class
        can set their specific endpoint as a class
        variable and get it using this prop.
        """
        return self.__class__.ENDPOINT or ""

    @property
    def list_model(self):
        """
        Each resource define their specific response model 
        as a class variable that can be used via this 
        property. this property handles the model
        used when listing multiple items.
        """
        return self.__class__.RESPONSE_MODEL_LIST

    @property
    def single_model(self):
        """
        Each resource define their specific response model 
        as a class variable that can be used via this 
        property. this property handles the model
        used when getting single item.
        """
        return self.__class__.RESPONSE_MODEL_SINGLE


    def get(self, id):
        data = self.rest.get_item(self.ep, id)

        if data != {}:
            resource = self.single_model(**data)
            print(f"m: {self.__class__.RESPONSE_MODEL_SINGLE}")
            return resource    

    def get_all(self):
        response = []
        api_response = self.rest.query_items(self.ep)

        for resource in api_response:
            response.append(self.list_model(**resource))

        return response