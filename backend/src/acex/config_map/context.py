class ConfigMapContext:
    """
    Context object som accessas i configuration. 
    Importeras och används av CompiledLogicalNode
    och sätts som property på cln objektet.
    """
    
    def __init__(self, logical_node, configuration, integrations):
        self.logical_node = logical_node
        self.configuration = configuration
        self.integrations = integrations
    
    # Convenience properties för vanliga use cases
    @property
    def hostname(self):
        """Shortcut för logical_node.hostname"""
        return self.logical_node.hostname
        
    @property
    def role(self):
        """Shortcut för logical_node.role"""
        return self.logical_node.role
        
    @property
    def site(self):
        """Shortcut för logical_node.site"""
        return getattr(self.logical_node, 'site', None)
        
    @property
    def node_id(self):
        """Shortcut för logical_node.id"""
        return self.logical_node.id
