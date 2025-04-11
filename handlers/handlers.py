from pymodbus.client import ModbusTcpClient
import time 

class AlertaHandler:
    def __init__(self):
        self.DEVICE_IP = "192.168.10.105"  # IP do FEN20-4DIP-4DXP
        self.MODBUS_PORT = 502  # Porta padrão Modbus TCP
        self.OUTPUT_REGISTER_START = 0x0000  # Endereço de saída
        self.NUM_OUTPUTS = 4  # Número de saídas digitais
        self.client = ModbusTcpClient(self.DEVICE_IP, port=self.MODBUS_PORT)

    def activate_outputs(self):
        """Ativa as saídas por 5 segundos, reenviando o sinal continuamente."""
        if self.client.connect():
            print(f"Conectado a {self.DEVICE_IP}")

            start_time = time.time()
            while (time.time() - start_time) < 2:  # Mantém ativado por 5 segundos
                output_values = [1] * self.NUM_OUTPUTS
                response = self.client.write_coils(self.OUTPUT_REGISTER_START, output_values)

                if response.isError():
                    print("Erro ao ativar saídas!")
                    return
                
                print("Saídas ativadas. Reenviando sinal...")
                time.sleep(0.5)  # Envia o sinal a cada 0.5 segundos para manter ativo

            # Desativando as saídas após 5 segundos
            self.deactivate_outputs()
        else:
            print("Falha na conexão com o dispositivo.")

    def deactivate_outputs(self):
        # """Desativa as saídas digitais e fecha a conexão."""
        output_values = [0] * self.NUM_OUTPUTS
        response = self.client.write_coils(self.OUTPUT_REGISTER_START, output_values)
        
        if response.isError():
            print("Erro ao desativar saídas!")
        else:
            print("Saídas desativadas.")
        # print('k')
        self.client.close()