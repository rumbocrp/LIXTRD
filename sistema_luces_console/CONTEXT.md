# Sistema de Luces

Consola de señales por mercado y supervisión de operaciones en laboratorio sintético o cuenta MT5 demo.

## Language

**Veto del operador**:
Estado de parada que impide nuevas operaciones simuladas y solicita cerrar las abiertas cuando existe una cotización válida. Permanece activo hasta una reanudación explícita.
_Avoid_: Pausa de pantalla, silenciado de alertas

**Reanudación**:
Acción explícita del operador que retira el veto manual. Un reinicio, una reconexión o repetir la activación del veto no constituyen una reanudación.
_Avoid_: Alternar veto, reconectar


**Presupuesto de pérdidas**:
Límite de 200 USD cuyo saldo disminuye con pérdidas cerradas, incluidas comisiones. Las ganancias no lo reponen y un cierre no se cuenta dos veces. La delimitación de la sesión diaria se acuerda por separado.
_Avoid_: Saldo de la cuenta, pérdidas compensadas con ganancias

**MT5 demo**:
Entorno de operaciones con fondos virtuales en una cuenta identificada por el terminal como demo. Sus cotizaciones, contratos y ejecuciones dependen del broker.
_Avoid_: Laboratorio sintético, cuenta real

**Laboratorio sintético**:
Entorno local con datos y ejecuciones simulados para pruebas reproducibles. Sus resultados se distinguen de operaciones confirmadas en MT5 demo.
_Avoid_: Ejecución del broker

**Símbolo del broker**:
Identificador de un instrumento concreto disponible en el servidor de la cuenta, con su contrato, unidades y condiciones de negociación. Un nombre de mercado solicitado por el operador necesita una correspondencia verificada con ese símbolo.
_Avoid_: Nombre universal, equivalencia automática entre índice y CFD
