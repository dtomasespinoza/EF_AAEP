const $ = (selector) => {
  const elemento = document.querySelector(selector);
  if (!elemento) {
    throw new Error(`No se encontro el elemento ${selector} en el DOM`);
  }
  return elemento;
};

const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function avisar(mensaje, tipo = "info", duracion = 4200) {
  const contenedor = $("#notificaciones");
  const elemento = document.createElement("div");

  elemento.className = `notificacion notificacion--${tipo}`;
  elemento.setAttribute("role", tipo === "error" ? "alert" : "status");

  const texto = document.createElement("div");
  texto.className = "notificacion__texto";
  texto.textContent = mensaje;

  const cerrar = document.createElement("button");
  cerrar.className = "notificacion__cerrar";
  cerrar.textContent = "×";
  cerrar.setAttribute("aria-label", "Cerrar aviso");
  cerrar.addEventListener("click", () => elemento.remove());

  elemento.append(texto, cerrar);
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

let peticionesEnCurso = 0;

function marcarCarga(inicio) {
  peticionesEnCurso += inicio ? 1 : -1;
  $("#cargando").classList.toggle("activo", peticionesEnCurso > 0);
}

class Api {

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

const FORMATO = new Intl.NumberFormat("es-CO", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

function peso(valor) {
  return `${FORMATO.format(Number(valor) || 0)} kg`;
}

function entero(valor) {
  return new Intl.NumberFormat("es-CO").format(Number(valor) || 0);
}

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

function escapar(texto) {
  return String(texto ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function elemento(etiqueta, atributos = {}, texto = "") {
  const nodo = document.createElement(etiqueta);

  for (const [clave, valor] of Object.entries(atributos)) {
    if (clave === "clase") {
      nodo.className = valor;
    } else if (clave === "texto") {
      nodo.textContent = valor;
    } else if (clave === "estilo") {

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

function agregar(contenedor, ...hijos) {
  for (const hijo of hijos) {
    if (hijo) {
      contenedor.appendChild(hijo);
    }
  }
  return contenedor;
}

function clasePeso(pesoKg, capacidad) {
  const proporcion = (Number(pesoKg) || 0) / (Number(capacidad) || 30);

  if (proporcion >= 0.75) return "lleno";
  if (proporcion >= 0.5) return "alto";
  return "";
}

function confirmarAccion(mensaje) {
  return window.confirm(mensaje);
}

function alPresionarEnter(elemento, accion) {
  elemento.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.repeat) {
      evento.preventDefault();
      accion();
    }
  });
}

function vaciar(contenedor) {
  while (contenedor.firstChild) {
    contenedor.removeChild(contenedor.firstChild);
  }
  return contenedor;
}

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

async function cargarCatalogo() {
  return Api.enviar("/api/catalogo");
}

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
