import modbus_tk.modbus_tcp as modbus_tk  # Import Modbus TCP library

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

class AlertaHander:
    def __init__(self):
        self.alert_state = False
        # Initialize Modbus TCP client
        self.modbus_client = modbus_tk.TcpMaster(host='192.168.1.100', port=502)
        self.modbus_client.set_timeout(5.0)  # Set a timeout for Modbus communication

    def process_alert(self, alert_value):
        self.alert_state = alert_value

        if self.alert_state:
            print(f"[AlertHander] Alert State: {self.alert_state}")
            try:
                # Write to Modbus coil (address 0, value 1)
                self.modbus_client.execute(
                    self.modbus_client.write_single_coil(0, 1)
                )
                print(f"[AlertHander] Coil at address {0} set to 1.")
            except Exception as e:
                print(f"[AlertHander] Error writing to Modbus coil: {e}")
            finally:
                self.alert_state = False  # Reset alert state
