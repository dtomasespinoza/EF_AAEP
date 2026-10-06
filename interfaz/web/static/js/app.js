/* ==========================================================================
   app.js
   ======
   Capa de comunicacion con la API y utilidades compartidas por las paginas.

   Se escribio en JavaScript plano, sin frameworks ni dependencias, por dos
   razones: el proyecto es de un curso donde lo que se evalua es el
   algoritmo, y anadir un framework exigiria instalar Node.js en cada
   equipo. Con `fetch` y unas pocas funciones auxiliares se resuelve todo
   lo necesario.

   ORGANIZACION
     1. Referencias al DOM
     2. Notificaciones y estado de carga
     3. Cliente HTTP
     4. Formateo de datos
     5. Utilidades de interfaz
   ========================================================================== */

/* ==========================================================================
   1. REFERENCIAS AL DOM
   ========================================================================== */

/** Selector de un solo elemento. Lanza error si no existe. */
const $ = (selector) => {
  const elemento = document.querySelector(selector);
  if (!elemento) {
    throw new Error(`No se encontro el elemento ${selector} en el DOM`);
  }
  return elemento;
};

/** Selector de varios elementos. Siempre devuelve un arreglo. */
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

/* ==========================================================================
   2. NOTIFICACIONES Y ESTADO DE CARGA
   ========================================================================== */

const ICONOS = {
  exito: "✓",
  error: "✕",
  alerta: "!",
  info: "i",
};

/** Muestra un aviso temporal en la esquina superior derecha. */
function avisar(mensaje, tipo = "info", duracion = 4200) {
  const contenedor = $("#notificaciones");
  const elemento = document.createElement("div");

  elemento.className = `notificacion notificacion--${tipo}`;
  elemento.setAttribute("role", tipo === "error" ? "alert" : "status");

  const icono = document.createElement("span");
  icono.className = "notificacion__icono";
  icono.textContent = ICONOS[tipo] || ICONOS.info;

  const texto = document.createElement("div");
  texto.className = "notificacion__texto";
  texto.textContent = mensaje;

  const cerrar = document.createElement("button");
  cerrar.className = "notificacion__cerrar";
  cerrar.textContent = "×";
  cerrar.setAttribute("aria-label", "Cerrar aviso");
  cerrar.addEventListener("click", () => elemento.remove());

  elemento.append(icono, texto, cerrar);
  contenedor.appendChild(elemento);

  if (duracion > 0) {
    setTimeout(() => {
      elemento.style.opacity = "0";
      elemento.style.transform = "translateX(36px)";
      elemento.style.transition = "opacity 200ms, transform 200ms";
      setTimeout(() => elemento.remove(), 200);
    }, duracion);
  }

  return elemento;
}

/* Un contador, no un booleano, para que dos peticiones simultaneas no se
   cancelen entre si al terminar una. */
let peticionesEnCurso = 0;

function marcarCarga(inicio) {
  peticionesEnCurso += inicio ? 1 : -1;
  $("#cargando").classList.toggle("activo", peticionesEnCurso > 0);
}

/* ==========================================================================
   3. CLIENTE HTTP
   ========================================================================== */

class Api {
  /**
   * Envia una peticion al servidor.
   *
   * Toda peticion devuelve la misma forma (`exito`, `mensaje`, `datos`),
   * asi que aqui solo hace falta desempaquetar y avisar los errores. La
   * funcion que llama se ocupa de los datos.
   */
  static async enviar(ruta, metodo = "GET", cuerpo = null) {
    marcarCarga(true);

    try {
      const opciones = {
        method: metodo,
        headers: {}
      };

      if (cuerpo instanceof FormData) {
        opciones.body = cuerpo;
      } else if (cuerpo !== null) {
        opciones.headers["Content-Type"] = "application/json";
        opciones.body = JSON.stringify(cuerpo);
      }

      const respuesta = await fetch(ruta, opciones);
      const texto = await respuesta.text();

      let datos;
      try {
        datos = JSON.parse(texto);
      } catch {
        throw new Error(`El servidor devolvio una respuesta ilegible (${respuesta.status})`);
      }

      if (!datos.exito) {
        throw new Error(datos.mensaje || "Ocurrio un error inesperado.");
      }

      return datos.datos;
    } catch (error) {
      if (error.name === "TypeError") {
        throw new Error("No se pudo conectar con el servidor. Revisa que siga ejecutandose.");
      }
      throw error;
    } finally {
      marcarCarga(false);
    }
  }

  static listar(filtros = {}) {
    const parametros = new URLSearchParams();

    for (const [clave, valor] of Object.entries(filtros)) {
      if (valor !== null && valor !== undefined && valor !== "") {
        parametros.set(clave, valor);
      }
    }

    const consulta = parametros.toString();
    return Api.enviar(`/api/pedidos${consulta ? `?${consulta}` : ""}`);
  }

  static registrar(datos) {
    return Api.enviar("/api/pedidos", "POST", datos);
  }

  static eliminar(codigo) {
    return Api.enviar(`/api/pedidos/${codigo}`, "DELETE");
  }

  static reabrir(codigo) {
    return Api.enviar(`/api/pedidos/${codigo}/reabrir`, "POST");
  }

  static buscar(codigo, algoritmo = "BINARIA") {
    return Api.enviar("/api/buscar", "POST", {
      codigo,
      algoritmo
    });
  }

  static compararBusqueda(codigo) {
    return Api.enviar("/api/buscar/comparar", "POST", {
      codigo
    });
  }

  static medirAlgoritmos(orden = "QUICKSORT") {
    const parametros = new URLSearchParams({
      orden_algoritmo: orden
    });
    return Api.enviar(`/api/algoritmos?${parametros}`);
  }

  static subirArchivo(archivo) {
    const datos = new FormData();
    datos.append("archivo", archivo);
    return Api.enviar("/api/carga/archivo", "POST", datos);
  }

  static planear(estrategia, prioritario, objetivo) {
    return Api.enviar("/api/salidas/plan", "POST", {
      estrategia,
      prioritario: prioritario || "",
      objetivo: objetivo || "CANTIDAD",
    });
  }

  static compararEstrategias(prioritario) {
    const parametros = new URLSearchParams();
    if (prioritario) {
      parametros.set("prioritario", prioritario);
    }
    return Api.enviar(`/api/salidas/estrategias?${parametros}`);
  }

  static confirmar(estrategia, prioritario, objetivo) {
    return Api.enviar("/api/salidas/confirmar", "POST", {
      estrategia,
      prioritario: prioritario || "",
      objetivo: objetivo || "CANTIDAD",
    });
  }

  static historial() {
    return Api.enviar("/api/salidas/historial");
  }

  static estadisticas() {
    return Api.enviar("/api/estadisticas");
  }

  static limpiar(tipo) {
    return Api.enviar("/api/limpiar", "POST", {
      tipo
    });
  }
}

/* ==========================================================================
   4. FORMATEO DE DATOS
   ========================================================================== */

const FORMATO = new Intl.NumberFormat("es-CO", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

/** Peso con una sola cifra decimal: "12.5 kg". */
function peso(valor) {
  return `${FORMATO.format(Number(valor) || 0)} kg`;
}

/** Numero sin decimales: "1.234". */
function entero(valor) {
  return new Intl.NumberFormat("es-CO").format(Number(valor) || 0);
}

/** Tiempo en milisegundos con la unidad mas legible. */
function duracion(milisegundos) {
  const valor = Number(milisegundos) || 0;

  if (valor < 1) {
    return "< 1 ms";
  }
  if (valor < 1000) {
    return `${valor.toFixed(1)} ms`;
  }
  return `${(valor / 1000).toFixed(2)} s`;
}

/**
 * Convierte texto de JavaScript en HTML seguro.
 *
 * Los datos vienen del servidor, pero un nombre de cliente podria contener
 * `<script>`. Insertar eso con innerHTML ejecutaria codigo. Se escapan los
 * cinco caracteres peligrosos antes de armar el HTML.
 */
function escapar(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Crea un elemento con sus atributos y su texto.
 *
 * Se prefiere a innerHTML para el contenido dinamico: al asignar `textContent`
 * no hay forma de que un dato se interprete como HTML, sin importar el
 * escaping previo.
 */
function elemento(etiqueta, atributos = {}, texto = "") {
  const nodo = document.createElement(etiqueta);

  for (const [clave, valor] of Object.entries(atributos)) {
    if (clave === "clase") {
      nodo.className = valor;
    } else if (clave === "texto") {
      nodo.textContent = valor;
    } else if (clave === "estilo") {
      // `estilo` es una abreviatura interna: `setAttribute("estilo", ...)`
      // crearia un atributo desconocido que el navegador ignora, y los
      // estilos NO se aplicarian. Hay que escribir en el atributo real.
      nodo.style.cssText = valor;
    } else if (valor !== null && valor !== undefined && valor !== false) {
      nodo.setAttribute(clave, valor);
    }
  }

  if (texto) {
    nodo.textContent = texto;
  }

  return nodo;
}

/** Inserta varios hijos, ignorando los nulos (condicionales en los templates). */
function agregar(contenedor, ...hijos) {
  for (const hijo of hijos) {
    if (hijo) {
      contenedor.appendChild(hijo);
    }
  }
  return contenedor;
}

/** Clase CSS del badge segun el porcentaje de ocupacion de un pedido. */
function clasePeso(pesoKg, capacidad) {
  const proporcion = (Number(pesoKg) || 0) / (Number(capacidad) || 30);

  if (proporcion >= 0.75) return "lleno";
  if (proporcion >= 0.5) return "alto";
  return "";
}

/* ==========================================================================
   5. UTILIDADES DE INTERFAZ
   ========================================================================== */

/** Pide confirmacion antes de una accion destructiva. */
function confirmarAccion(mensaje) {
  return window.confirm(mensaje);
}

/** Evita disparar la accion mientras la tecla Enter mantiene pulsada. */
function alPresionarEnter(elemento, accion) {
  elemento.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.repeat) {
      evento.preventDefault();
      accion();
    }
  });
}

/** Vacia un contenedor de contenido. */
function vaciar(contenedor) {
  while (contenedor.firstChild) {
    contenedor.removeChild(contenedor.firstChild);
  }
  return contenedor;
}

/** Inserta el bloque de "sin resultados" cuando una tabla no tiene filas. */
function mostrarVacio(contenedor, icono, titulo, texto) {
  const vacio = elemento("div", {
    clase: "vacio"
  });
  vacio.append(
    elemento("div", {
      clase: "vacio__icono",
      texto: icono
    }),
    elemento("h4", {
      texto: titulo
    }),
    elemento("p", {
      texto
    })
  );
  vaciar(contenedor).appendChild(vacio);
}

/**
 * Actualiza el resumen de la barra lateral.
 *
 * Se llama desde varias paginas, asi que se resuelve el elemento de forma
 * opcional: si la pagina no lo tiene, no falla.
 */
async function refrescarLateral() {
  const nodoPendientes = $("#lateral-pendientes");
  const nodoPeso = $("#lateral-peso");

  if (!nodoPendientes || !nodoPeso) {
    return;
  }

  try {
    const datos = await Api.estadisticas();
    nodoPendientes.textContent = entero(datos.resumen.pendientes);
    nodoPeso.textContent = peso(datos.resumen.peso_pendientes);
  } catch {
    nodoPendientes.textContent = "—";
    nodoPeso.textContent = "—";
  }
}

/** Carga el catalogo de enums que viene del nucleo. */
async function cargarCatalogo() {
  return Api.enviar("/api/catalogo");
}

/** Rellena un `<select>` con las opciones recibidas. */
function llenarSelect(select, opciones, valorInicial) {
  vaciar(select);

  for (const opcion of opciones) {
    const nodo = elemento("option", {
      value: opcion.valor,
      texto: opcion.etiqueta
    });
    if (opcion.valor === valorInicial) {
      nodo.selected = true;
    }
    select.appendChild(nodo);
  }

  return select;
}

function tablaPedidos(contenedor, pedidos, acciones = null) {
  vaciar(contenedor);
  const caja = elemento('div', {
      clase: 'tabla-scroll'
    }),
    tabla = elemento('table');
  const encabezado = elemento('tr');
  ['Código', 'Peso', 'Distrito', 'Dirección', 'Cliente', 'Teléfono', 'Estado', ...(acciones ? ['Acciones'] : [])].forEach(t => encabezado.append(elemento('th', {
    texto: t
  })));
  const head = elemento('thead');
  head.append(encabezado);
  tabla.append(head);
  const body = elemento('tbody');
  pedidos.forEach(p => {
    const fila = elemento('tr');
    [p.codigo, peso(p.peso), p.distrito || '—', p.direccion || '—', p.cliente || '—', p.telefono || '—', p.estado || '—'].forEach(t => fila.append(elemento('td', {
      texto: t
    })));
    if (acciones) {
      const celda = elemento('td');
      acciones(celda, p);
      fila.append(celda);
    }
    body.append(fila);
  });
  tabla.append(body);
  caja.append(tabla);
  contenedor.append(caja);
  if (!pedidos.length) contenedor.append(elemento('p', {
    texto: 'No hay pedidos para mostrar.'
  }));
}
