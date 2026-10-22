# DJI RC Pro Enterprise & RC-N1 — Plug-and-Play Simulator Emulator (Zero-Delay + Auto-Driver)

Transforma controles **DJI RC Pro Enterprise (RM510B)**, **DJI RC-N1 (Air 2S / Mini 2 / Mavic 3)**, **DJI RC (RM330)** e **DJI RC 2** em um controle **Xbox 360 Virtual** com **latência zero** para rodar no **DJI Virtual Flight**, **Liftoff**, **VelociDrone**, **Uncrashed** e **TRYP FPV**.

---

## 🚀 Principais Melhorias e Engenharia Aplicada

1. **Suporte ao DJI RC Pro Enterprise (`VID_2CA3` / `PID_1021` — RM510B)**
   - Adicionado suporte nativo via USB Bulk (`EP_OUT 0x01` / `EP_IN 0x81`) e detecção híbrida automática **USB Bulk + Serial VCOM** (para **DJI RC-N1 / Air 2S**).

2. **Correção do Bug de 1 Segundo de Delay no Protocolo DUML ([`DJI-RC-Emulator/src/duml.py`](DJI-RC-Emulator/src/duml.py))**
   - **Causa raiz descoberta:** O pacote `read_sticks` (`cmd_set=0x06, cmd_id=0x01`) usava um número de sequência estático (`0x34EB`). No firmware do **DJI RC Pro Enterprise**, requisições com o mesmo `seq_num` faziam o controle responder com amostra em cache atualizada a apenas **0.8 Hz (~1,05s de atraso)**.
   - **Solução:** Implementado incremento dinâmico de 16 bits (`_next_seq()`) com recálculo de CRC-16 a cada leitura, elevando a taxa real de atualização dos sticks e do gimbal de **0.8 Hz para +50 Hz em tempo real (Zero Delay)**.

3. **100% Plug-and-Play Sem Zadig + Correção Automática do Erro Código 31 do Windows ([`DJI-RC-Emulator/src/auto_driver.py`](DJI-RC-Emulator/src/auto_driver.py))**
   - **Causa raiz no Windows 10/11:** O descritor USB do DJI RC Pro Enterprise grava simultaneamente `DeviceInterfaceGUID` e `DeviceInterfaceGUIDs` na chave `Device Parameters` do Registro, fazendo o driver `WinUSB.sys` falhar com **Código 31 (`CM_PROB_FAILED_ADD` / `0xC0000182`)**.
   - **Solução:** O módulo [`auto_driver.py`](DJI-RC-Emulator/src/auto_driver.py) traz os catálogos assinados (`WinUSB` e `DJI VCOM`) embutidos, instala o certificado e o driver via `pnputil`, limpa a chave duplicada do Registro, reinicia a interface USB e instala o `ViGEmBus` automaticamente na primeira execução — **sem precisar baixar ou usar o Zadig**.

4. **Arquitetura Dual-Thread + Controle Suave da Rodinha do Gimbal ([`DJI-RC-Emulator/tk_main.py`](DJI-RC-Emulator/tk_main.py))**
   - **Thread dedicada de leitura contínua** esvaziando o buffer USB IN em tempo real (fila de 0 ms no SO) + **Thread de escrita cadenciada**.
   - Curva exponencial suave + modulação proporcional para a **rodinha do gimbal (`scroll` / `camera`)**, permitindo controlar a inclinação da câmera suavemente no **DJI Virtual Flight** sem saltos ("socos") e sem precisar instalar bibliotecas pesadas (`Tkinter` nativo).

---

## 🎮 Controles Suportados

| Controle | Modelo / PID | Modo de Conexão | Status |
|---|---|---|---|
| **DJI RC Pro Enterprise** | `RM510B` (`0x1021`) | USB-C Bulk (WinUSB automático) | ✅ Testado (Zero Delay + Gimbal) |
| **DJI RC-N1 (Air 2S / Mini 2 / Mavic 3)** | `RC231` (`0x001F` / `0x0036`) | USB-C Serial VCOM / Bulk | ✅ Suportado |
| **DJI RC** | `RM330` (`0x1023`) | USB-C Bulk | ✅ Suportado |
| **DJI RC 2 / RC-N2 / RC-N3** | `0x0047` / `0x0082` / `0x003B` | USB-C Bulk | ✅ Suportado |

---

## ⚡ Como Usar (Plug and Play)

1. **Instale o Simulador (se ainda não tiver):** dê dois cliques em **[`instalar_simulador_dji.bat`](instalar_simulador_dji.bat)** (ele executa o instalador local `1661500931886-DJI Virtual Flight.exe` se estiver no pendrive, ou baixa automaticamente a versão oficial de PC direto do CDN da DJI: [Download Direto DJI Virtual Flight PC (3.0 GB)](https://dl.djicdn.com/downloads/dji_virtual_flight/20220826/1661500931886-DJI%20Virtual%20Flight.exe)).
2. Conecte o controle DJI ligado ao PC pela porta **USB-C de baixo**.
3. Dê dois cliques em **[`start.bat`](start.bat)**:
   - Se for um PC novo, o próprio [`start.bat`](start.bat) instala automaticamente o Python (se não houver), as bibliotecas (`vgamepad`, `pyusb`, `libusb`, `pyserial`), o driver do controle virtual Xbox 360 (`ViGEmBus`) e o driver USB da DJI sem Zadig.
4. Abra o **DJI Virtual Flight** (ou outro simulador FPV) e voe!

---

## 📄 Licença e Créditos

- Baseado no projeto original [DJI-RC-Emulator](https://github.com/deviverr/DJI-RC-Emulator) (MIT License).
- Engenharia reversa de protocolo DUML (`RM510B`), correção de latência, suporte ao gimbal no DJI Virtual Flight e automação Plug-and-Play WinUSB/Code 31 por **Vicente** ([@rojaooo](https://github.com/rojaooo)).
