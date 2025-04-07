
class CancelHandler:
    isCanceled = False

    @classmethod
    def get_isCanceled_value(cls):
        return cls.isCanceled
    
    @classmethod
    def set_isCanceled_value(cls, new_isCanceled_value):
        cls.isCanceled = new_isCanceled_value

class EtiquetaHandler:
    quantidade_etiqueta = 0
    valor_etiqueta = None
    
    @classmethod
    def set_valor_etiqueta(cls, new_valor_etiqueta):
        cls.valor_etiqueta = new_valor_etiqueta
    
    @classmethod
    def set_quantidade_etiqueta(cls, new_quantidade_etiqueta):
        cls.quantidade_etiqueta += new_quantidade_etiqueta
    
    @classmethod
    def get_valor_etiqueta(cls):
        return cls.valor_etiqueta
    
    @classmethod
    def get_quantidade_etiqueta(cls):
        return cls.quantidade_etiqueta
    
    @classmethod
    def set_quantidade_etiqueta_zero(cls):
        cls.quantidade_etiqueta = 0
