-- Datos de prueba para Constructora Altura (Mock Data)
-- Permite probar la aplicación en Streamlit mientras se consiguen los datos reales.

-- 1. Usuarios del sistema
INSERT INTO USUARIO (id_usuario, nombre, email, rol, password_hash) VALUES
(1, 'Vicente Acevedo', 'vicente@altura.cl', 'Administrador', 'hash_falso_123'),
(2, 'Thannia', 'thannia@altura.cl', 'Proyectista', 'hash_falso_456');

-- 2. Clientes
INSERT INTO CLIENTE (id_cliente, rut, razon_social, direccion, email_contacto) VALUES
(1, '76.123.456-7', 'Inmobiliaria Norte SpA', 'Av. Apoquindo 1234, Las Condes', 'contacto@norte.cl'),
(2, '15.987.654-3', 'Juan Pérez', 'Calle Falsa 123, La Florida', 'juan.perez@gmail.com');

-- 3. Teléfonos de Clientes (Demuestra la 1FN)
INSERT INTO TELEFONO_CLIENTE (id_cliente, nro_telefono, numero, tipo_telefono) VALUES
(1, 1, '+56912345678', 'Celular Gerente'),
(1, 2, '+56223456789', 'Oficina Central'),
(2, 1, '+56987654321', 'WhatsApp Personal');

-- 4. Catálogo Maestro de Partidas (Materiales y Servicios)
INSERT INTO PARTIDA (id_partida, codigo, descripcion, unidad, costo_referencial) VALUES
(1, 'OBR-01', 'Trazado y niveles', 'GL', 150000),
(2, 'HOR-01', 'Hormigón H30 fundaciones', 'm3', 85000),
(3, 'VOL-01', 'Suministro e instalación Volcanita ST 15mm', 'm2', 7500),
(4, 'PIN-01', 'Pintura esmalte al agua interior', 'm2', 3500),
(5, 'CER-01', 'Cerámica piso 45x45', 'm2', 12000);

-- 5. Contratistas Especializados
INSERT INTO CONTRATISTA (id_contratista, rut, nombre, especialidad, email, telefono) VALUES
(1, '77.555.444-1', 'Electricidad Voltaje Ltda', 'Eléctrica', 'ventas@voltaje.cl', '+56911112222'),
(2, '12.333.222-K', 'Gasfitería San Juan', 'Sanitaria', 'sanjuan@gasfiteria.cl', '+56933334444');
