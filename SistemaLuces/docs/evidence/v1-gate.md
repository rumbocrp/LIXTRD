# Gate vigente de realineación

**Corte:** 2026-08-30  
**Producto:** `BLOCKED_REBASELINE`  
**G-R0 técnico:** `PASS_TECNICO`  
**Aprobación del dueño:** pendiente

## Alcance

Este gate sustituye la certificación narrativa del primer intento. Sólo evalúa R0:
autoridad, organización documental, trazabilidad, aislamiento del legado y garantía de que
Trading Journal se trató como referencia de solo lectura.

No certifica código, conexión demo, modelo, interfaz ni readiness operativo.

## Evidencia requerida

- salida exit 0 de `python3.11 -B scripts/verificar_documentacion.py`;
- ausencia de claims históricos en los documentos de autoridad;
- HEAD y estado final de Trading Journal comprobados sin escribir en ese repositorio;
- documentación anterior conservada bajo `docs/legacy/`;
- veredicto de producto mantenido en `BLOCKED_REBASELINE`.

## Resultado

Comando ejecutado desde la raíz del repositorio:

```bash
python3.11 -B scripts/verificar_documentacion.py
```

Resultado observado: exit code `0`; archivos canónicos, autoridad, links y aislamiento de
legado en PASS. La comprobación final del Trading Journal conserva el HEAD auditado
`89ba62b55b8ea079838d9130bb61f42497da965d`; no se realizaron escrituras en ese repositorio.

`G-R0` queda en `PASS_TECNICO`; la aceptación del dueño permanece separada.

Las Puertas `G-R1`…`G-R7` permanecen bloqueadas y no heredan el resultado de R0.
