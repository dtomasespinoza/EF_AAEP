# RAPPIDOS - Sistema de pedidos

RAPPIDOS organiza las entregas de una tienda: registra pedidos, decide **qué
pedidos caben en el vehículo de 30 kg**, los despacha y guarda el historial.

El proyecto tiene **dos interfaces** (web y consola) sobre **un solo núcleo** de
lógica y algoritmos. Los algoritmos están escritos a mano y "instrumentados":
además del resultado, reportan cuántas comparaciones, cuántos intercambios y
cuánto tardaron, porque lo que se evalúa es el algoritmo, no la interfaz.

---

## 1. Instalación

Probado en **Python 3.13**. La sintaxis no usa nada posterior a 3.9, que es
justo lo que pide Flask 3.1, así que debería funcionar desde esa versión en
adelante.

```bash
pip install -r requirements.txt
```

| Dependencia | Versión | Para qué |
|---|---|---|
| Flask | 3.1.3 | Servidor web de la interfaz |
| openpyxl | 3.1.5 | Leer archivos `.xlsx` en la carga masiva |
| gunicorn | 26.2.0 | Servidor de producción (Linux; en Windows no se usa) |

`openpyxl` es el único extra del núcleo: si no está instalado, el resto del
sistema funciona igual y solo se pierde la importación de Excel. `gunicorn`
solo hace falta en el servidor donde se publica; en Windows se sigue usando el
servidor de Flask de desarrollo.

## 2. Cómo ejecutarlo

```bash
python app.py     # Interfaz web  ->  http://127.0.0.1:5000
python main.py    # Interfaz de consola, con menus de texto
```

En producción **no** se usa `python app.py`, sino el punto de entrada WSGI de
`wsgi.py` con un servidor real (ver la sección 10).

Variables de entorno opcionales:

| Variable | Por defecto | Para qué |
|---|---|---|
| `PUERTO` | `5000` | Puerto del servidor web |
| `MODO_DEBUG` | `1` | `0` desactiva la recarga automática de Flask |
| `RAPPIDOS_ARCHIVO` | `datos/pedidos.json` | Dónde se guardan los pedidos |

## 3. Pruebas

No hace falta ningún framework de tests: son dos scripts que se ejecutan con
`python` y avisan `[OK]` o `[FALLA]` en cada caso.

```bash
python tests/prueba_api.py       # Extremo a extremo de la API y de las paginas
python tests/prueba_consola.py   # Cada opcion del menu de la consola
```

Ambas pruebas usan un archivo de datos temporal, así que **no tocan los pedidos
reales**. Entre las dos cubren el registro, la validacion de pesos, la carga
masiva, los seis ordenamientos, la busqueda binaria y lineal, las tres
estrategias de reparto con y sin pedido prioritario, la confirmacion de la
salida, el historial, el borrado y el manejo de errores.

## 4. Estructura del proyecto

```
ProyectoFinal/
├── app.py                  Servidor Flask: paginas + API JSON
├── wsgi.py                 Punto de entrada WSGI para produccion
├── main.py                 Consola con menus
├── requirements.txt
├── datos/                  pedidos.json (se crea solo, no se versiona)
├── nucleo/                 LOGICA PURA: no importa Flask, ni input, ni print
│   ├── modelos.py          Pedido, enums, resultado de operacion
│   ├── algoritmos.py       6 ordenamientos + 2 busquedas, con metricas
│   ├── reparto.py          First-Fit, Best-Fit y Mochila 0/1
│   ├── repositorio.py      Persistencia JSON con escritura atomica
│   ├── generador.py        Pedidos y direcciones aleatorios
│   ├── importador.py       Importacion de CSV, TXT y XLSX
│   ├── servicio.py         Fachada RAPPIDOS: todos los casos de uso
│   └── serializador.py     Respuestas JSON uniformes
├── interfaz/web/
│   ├── templates/          base + 5 paginas + 404
│   └── static/
│       ├── css/estilos.css  Diseno responsive, sin frameworks
│       └── js/app.js        Cliente HTTP y utilidades, en JavaScript plano
├── legado/                 Consola original, guardada sin tocar
└── tests/
```

### La regla de arquitectura

> `nucleo/` no importa nada de las interfaces. No conoce `input`, `print`,
> Flask ni HTML. Todo lo que entra sale por funciones que devuelven
> estructuras de datos.

Es la razón por la que la web y la consola no repiten ni una línea de negocio:
las dos llaman a `nucleo.servicio.RAPPIDOS`. También es lo que permite que
`nucleo/` se pueda probar sin levantar un servidor.

## 5. Qué hace el sistema

- **Registrar pedidos** con peso, dirección, cliente y teléfono. El código
  (`P001`, `P002`, …) se genera solo y el contador se guarda en disco, así que
  no se repite al reiniciar.
- **Carga masiva**: generar pedidos aleatorios con direcciones colombianas o
  importar desde `.csv`, `.txt` y `.xlsx`. Las filas inválidas se reportan una
  por una con su número de línea, y las válidas se cargan igual.
- **Filtrar y ordenar** por peso, con cualquiera de los seis algoritmos.
- **Buscar** un pedido por código con búsqueda binaria o lineal.
- **Planear la salida** de tres maneras y **compararlas** sobre los mismos
  datos antes de decidir.
- **Confirmar la salida**: los pedidos quedan `DESPACHADO` con su fecha, no se
  borran, y la salida queda en el historial.
- **Estadísticas**: totales, peso pendiente, rango, viajes necesarios,
  histograma de pesos y zonas más pedidas.

## 6. Los algoritmos

### Ordenamiento (compara 6 sobre la misma lista)

| Algoritmo | Tiempo | Memoria extra | Nota |
|---|---|---|---|
| Burbuja | O(n²) | O(1) | La más simple, la que peor escala |
| Inserción | O(n²) | O(1) | Muy rápida si la lista ya casi está ordenada |
| QuickSort | O(n log n) promedio | O(log n) | La usada para ordenar de verdad |
| Conteo | **O(n + k)** | O(n + k) | La unica con O(n + k) *garantizado* |
| Cubetas | O(n + k) promedio | O(n + k) | |
| Nativo (`sorted`) | O(n log n) | O(n) | Línea base de Python |

`k` es el rango de valores. En RAPPIDOS los pesos van de 0 a 30 kg con dos
decimales, así que en céntimas el rango es de 3000: el conteo resuelve el
problema con menos comparaciones que el resto.

El **conteo** necesita un detalle fácil de equivocar: los índices se calculan
sobre el peso **multiplicado por 10^decimales**. Si se truncara cada peso con
`int(peso)`, un pedido de 8.21 kg y otro de 8.71 kg caerían en la misma
posición y el orden final sería incorrecto.

### Búsqueda

| Algoritmo | Tiempo | Requisito |
|---|---|---|
| Lineal | O(n) | Ninguno |
| Binaria | O(log n) | La lista **debe** estar ordenada |

El sistema normaliza el código a mayúsculas (`p001` encuentra a `P001`) y
compara ambos algoritmos para mostrar la diferencia de comparaciones.

### Reparto del vehículo

| Estrategia | Idea | Complejidad |
|---|---|---|
| Primero que cabe (First-Fit Decreasing) | Ordena de mayor a menor y toma el primero que cabe | O(n log n) |
| Mejor encaje (Best-Fit Decreasing) | Toma el que deja el menor espacio sobrante | O(n²) |
| Mochila 0/1 | Programa dinámica: **el óptimo**, garantiza la mejor combinación | O(n · C) |

Las dos heurísticas son **voraces** (*greedy*): eligen el mejor candidato del
momento sin pensar en el resto, y eso no siempre es la mejor combinación. Por
eso el sistema trae la mochila 0/1 como referencia. Se puede comprobar en la web
o en la consola: con los mismos pedidos, las heurísticas suelen dejar espacio
sin usar y la mochila 0/1 entrega más pedidos.

El objetivo de la mochila es configurable: **maximizar el número de pedidos** o
**maximizar los kilos transportados**.

Si hay más de 800 pedidos pendientes, la mochila degrada a Best-Fit
deliberadamente: su tabla tendría `n x 3001` celdas, y con 800 pedidos serían
2.4 millones, más de lo que conviene reservar sin avisar. El mensaje del plan
indica qué degradación se aplicó.

### Pedido prioritario

El pedido marcado como prioritario se carga **siempre primero** y se descuenta
de la capacidad antes de llenar el resto. Si el usuario lo eligió, se lleva:
no se descarta por ser pesado.

## 7. Detalles de ingeniería

**Escritura atómica.** El archivo JSON se escribe primero en un temporal y
luego se renombra con `os.replace`. Si el programa se cierra a mitad de una
escritura, el archivo original queda intacto en vez de corrupto.

**Contador persistido.** El código del próximo pedido se guarda en el JSON. Si
no, al recargar volvería a `P001` y se pisarían pedidos existentes. Como red de
seguridad, si el JSON fue editado a mano y no trae ese campo, el contador se
deduce del código más alto que exista.

**Validación en un solo lugar.** El peso se valida en `servicio.registrar`, no
en la web ni en la consola. Las dos interfaces mandan el mismo dato y reciben
el mismo error. Acepta coma decimal (`2,75`) porque en un teclado español el
separador es la coma.

**Plan recalculado en el servidor.** Al confirmar una salida, el servidor
vuelve a calcular el plan en lugar de confiar en los códigos que envía el
navegador. Si se aceptara la lista del cliente, alguien podría manipularla a
mano y despachar pedidos que nunca estuvieron en el plan.

**Un sobre de respuesta único.** Toda la API responde
`{exito, mensaje, datos}`. El cliente solo tiene que desempaquetar y mostrar
`mensaje` cuando `exito` es falso; no hay que comprobar rutas distintas.

**Sin `innerHTML`.** El JavaScript construye los elementos con
`textContent` y `createElement`, y los datos que vienen del servidor nunca se
interpretan como HTML. Es la defensa directa contra un nombre de cliente que
contenga `<script>`.

**Codificación UTF-8.** El código, los comentarios y los mensajes están
escritos en UTF-8, que es el valor por defecto de Python 3. Si en una consola
antigua de Windows las tildes se ven mal, no es un problema del programa: es la
codificación de esa ventana. Se arregla con `chcp 65001` antes de ejecutar, o
con `set PYTHONIOENCODING=utf-8`.

## 8. La API

Todas las rutas devuelven `{exito, mensaje, datos}`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/pedidos` | Lista con filtros `peso_min`, `peso_max`, `solo_pendientes`, `orden`, `descendente` |
| POST | `/api/pedidos` | Registra un pedido |
| DELETE | `/api/pedidos/<codigo>` | Elimina un pedido |
| POST | `/api/pedidos/<codigo>/reabrir` | Devuelve un despachado a pendientes |
| POST | `/api/pedidos/<codigo>/priorizar` | Planea forzando ese pedido como prioritario |
| POST | `/api/buscar` | Busca por código (`algoritmo`: `BINARIA` o `LINEAL`) |
| POST | `/api/buscar/comparar` | Ejecuta ambas búsquedas y contrasta el coste |
| GET | `/api/algoritmos` | Mide los 6 ordenamientos |
| POST | `/api/carga/generar` | Genera pedidos aleatorios |
| POST | `/api/carga/archivo` | Importa CSV / TXT / XLSX |
| GET | `/api/carga/plantilla` | Descarga un CSV de ejemplo |
| POST | `/api/salidas/plan` | Simula una salida **sin** despachar |
| GET | `/api/salidas/estrategias` | Compara las 3 estrategias |
| POST | `/api/salidas/confirmar` | Confirma y despacha |
| GET | `/api/salidas/historial` | Historial de salidas |
| GET | `/api/estadisticas` | Métricas del panel |
| POST | `/api/limpiar` | Vacía pendientes o todo |
| GET | `/api/catalogo` | Enums del núcleo, para construir los menús |

`/api/catalogo` existe para que los menús de la interfaz no repitan los
nombres de los algoritmos a mano: se leen del código, así que una estrategia
nueva aparece en la web sin tocar el JavaScript.

## 9. La consola

`main.py` es el mismo sistema en modo texto: 11 opciones que cubren registro,
listado, generación, importación, búsqueda, medición de algoritmos, plan de
salida, objetivo de la mochila, estadísticas, historial y borrado.

Se conserva como modo de uso del sistema porque es el más cómodo para
demostrar el comportamiento de los algoritmos en clase: se ve el menú, se
escribe el dato y se observa cuántas comparaciones hizo el algoritmo.

La consola **original**, tal como estaba antes de la modernización, quedó en
`legado/` sin tocar, como referencia histórica.

## 10. Publicación en internet

### Qué se puede y qué no se puede subir gratis

RAPPIDOS guarda los pedidos en **un archivo del disco**, `datos/pedidos.json`.
Eso decide dónde se puede publicar:

| Plataforma | Disco persistente | Sirve tal cual |
|---|---|---|
| **PythonAnywhere** (plan gratuito) | Sí, 512 MB | **Sí** |
| Vercel, Render Free, Cloud Run | No (disco efímero) | No: se perderían los pedidos |
| Railway, Fly.io, Render con volumen | Sí, de pago | Sí, pagando |

Vercel y los demás *serverless* ejecutan el código en una máquina temporal que
se destruye tras cada arranque en frío. El JSON se volvería a crear vacío y los
pedidos desaparecerían solos. Para usarlos habría que reescribir
`nucleo/repositorio.py` contra una base de datos externa (Neon, Supabase,
PlanetScale), lo que es un proyecto aparte.

Por eso el despliegue documentado usa **PythonAnywhere**, que da un disco real
y por lo tanto no obliga a tocar una sola línea del sistema.

### GitHub

```bash
git init
git add .
git commit -m "RAPPIDOS: sistema de pedidos con nucleo comun"
git remote add origin https://github.com/<TU_USUARIO>/ProyectoFinal.git
git push -u origin main
```

`.gitignore` excluye `datos/`, los entornos virtuales y `__pycache__`, así que
la base de datos de cada máquina no se versiona.

### PythonAnywhere

1. Crear una cuenta gratuita en
   [pythonanywhere.com](https://www.pythonanywhere.com).
2. Abrir la **consola Bash** y clonar el repositorio:

   ```bash
   git clone https://github.com/<TU_USUARIO>/ProyectoFinal.git
   cd ProyectoFinal
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. En la pestaña **Web**, crear una app: tipo **Flask**, y en el campo de la
   ruta del código fuente poner:

   ```
   /home/<TU_USUARIO>/ProyectoFinal/wsgi.py
   ```

4. Pulsar **Reload**. Queda publicada en
   `https://<TU_USUARIO>.pythonanywhere.com`.

`wsgi.py` es el módulo que le pide PythonAnywhere: importa el mismo objeto
`app` de Flask y lo expone como `application`, sin arrancar ningún servidor
adicional. Es exactamente lo que haría `gunicorn wsgi:application` en un
servidor con Linux.

**Nota sobre el plan gratuito:** la web app gratuita tiene vencimiento (Python
Anywhere la revisa periódicamente) y un límite de 100 segundos de CPU al día
para consolas. Para un proyecto académico de demostración es suficiente; si
hiciera falta más, el plan Developer cuesta 10 USD/mes.

### Actualizar tras un `git push`

```bash
cd ~/ProyectoFinal
git pull
```

No hace falta tocar la configuración ni reinstalar dependencias, salvo que
hayan cambiado las versiones de `requirements.txt` (entonces hay que volver a
ejecutar `.venv/bin/pip install -r requirements.txt`).

### Comprobación de que el servidor es de producción

El dato guardado se mantiene entre visitas, lo que prueba que el disco es
persistente:

```bash
curl -s https://<TU_USUARIO>.pythonanywhere.com/api/estadisticas
```
