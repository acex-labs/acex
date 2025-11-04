

class ConfigMap: 

    def __init__(self, *args, **kwargs):
        self._name = None
        self.args = args
        self.kwargs = kwargs
        self.filters = None

    @property
    def name(self):
        if self._name is not None:
            return self._name
        return self.__class__.__name__


    def compile(self, data):
        """
        Compiles the ConfigMap, this is where the actual 
        compilation logic should be implemented. This method 
        should be overridden in subclasses to provide specific 
        compilation behavior.
        """

        # DEN HÄR SKA SKRIVAS ÖVER MED RIKTIG LOGIK FRÅN RESPEKTIVE CHILDKLASS
        pass