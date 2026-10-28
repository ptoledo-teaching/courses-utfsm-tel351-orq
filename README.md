# ORQ - Orquestación cloud

Este laboratorio integra AWS CLI, AWS CloudFormation, Boto3 y AWS CDK. La actividad retoma la API HTTP del laboratorio sobre CloudFormation y la amplía con un registro de estaciones de la HoloNet. CDK describe la infraestructura, mientras un programa Boto3 descubre los recursos desplegados e incorpora los datos iniciales.

El trabajo es individual y se realiza en AWS CloudShell, utilizando AWS Management Console con la interfaz en inglés para inspeccionar el despliegue. La actividad dura 70 minutos, incluyendo la presentación inicial, la preparación del proyecto y la evaluación. La limpieza se realiza después del bloque.

## Resultados esperados

Al completar el laboratorio, será posible:

1. Relacionar una aplicación CDK con el template de CloudFormation generado y el stack desplegado
2. Completar las referencias y los permisos que conectan una Lambda function con DynamoDB
3. Descubrir recursos desde los outputs de un stack mediante AWS CLI y Boto3
4. Inicializar datos mediante escrituras condicionales que conserven los registros existentes
5. Distinguir el despliegue de recursos, la inicialización de datos y la operación de un sistema

## Contexto

La HoloNet es la red de telecomunicaciones de la República Galáctica. Permite transmitir mensajes holográficos y otros datos mediante enlaces a través del hiperespacio. Su operación depende de estaciones distribuidas en distintos sectores, cuya disponibilidad debe mantenerse registrada para coordinar las tareas de mantenimiento.

Cada estación tiene un identificador, un nombre y un estado operacional: `ACTIVE`, `MAINTENANCE` u `OFFLINE`. El catálogo inicial permite comenzar a utilizar el sistema, pero sus estados cambian durante la operación. Volver a ejecutar la preparación no debe reemplazar esos cambios por los valores originales.

La API utilizará Lambda y DynamoDB para consultar las estaciones de un sector y actualizar su estado. CDK describirá los recursos y sus relaciones; CloudFormation administrará su despliegue. Después, un programa Boto3 encontrará la tabla mediante los outputs del stack y cargará las estaciones que todavía no existan.

Crear la tabla no equivale a preparar el catálogo. Una vez que el sistema está en operación, repetir la carga inicial debe incorporar las estaciones que falten sin reemplazar los registros existentes.

## Evaluación

La evaluación comprueba la infraestructura y los resultados de la actividad. No requiere un ejercicio adicional, un informe ni una entrega separada de código.

El sitio de evaluación está disponible en [https://lab09.shareddomain.link](https://lab09.shareddomain.link). Solicita el **AWS account ID** y el **RUT normalizado**, sin puntos ni guion y con `k` minúscula. Los recursos se descubrirán mediante los outputs de `tel351-orq`.

La evaluación utiliza el role `TEL351-Evaluator` configurado en los laboratorios anteriores. El role debe poder asumirse; esta condición no otorga puntos. Las comprobaciones serán independientes para permitir avances parciales. Los intentos podrán repetirse durante el bloque y quedarán registrados en un historial asociado al RUT.

| Aspecto | Puntaje |
| --- | ---: |
| Stack desplegado | 10 |
| Referencias, variables de entorno, routes y outputs | 10 |
| Permisos de Lambda limitados a las operaciones y la tabla requeridas | 15 |
| Catálogo inicial completo | 15 |
| Consulta de estaciones separada por sector | 10 |
| Actualización persistente del estado de una estación | 10 |
| Rechazo de estados inválidos y estaciones inexistentes | 10 |
| Conservación de datos después de repetir la inicialización | 20 |
| **Total** | **100** |

La conservación requiere comparar dos momentos. La **comprobación inicial** cambiará el estado de una estación mediante la API y registrará el resultado como referencia. Después de repetir la inicialización, una evaluación comprobará que la misma tabla y el registro conservaron ese cambio. Para registrar la referencia basta con que una estación pueda consultarse y actualizarse; no es necesario haber completado el catálogo.

El sitio indicará qué estación quedó como referencia. No modificarla manualmente durante esa secuencia. Las evaluaciones posteriores tampoco la modificarán ni reemplazarán automáticamente la referencia. Si es necesario comenzar otra secuencia, solicitar una nueva comprobación inicial; los intentos anteriores permanecerán en el historial.

## Actividad

### 1. Preparar el proyecto y el entorno CDK

#### 1.1 Obtener los materiales

1. Ingresar a CloudShell en `sa-east-1` con su identidad administrativa
2. Obtener una copia de los materiales del laboratorio:

   ```bash
   cd "$HOME"
   git clone https://github.com/ptoledo-teaching/courses-utfsm-tel351-orq.git
   ```

3. Utilizar AWS CLI para comprobar la cuenta, la identidad y la Región efectivas:

   ```bash
   aws sts get-caller-identity
   aws configure list
   ```

La carpeta `courses-utfsm-tel351-orq` contiene los materiales, no un proyecto CDK inicializado. El proyecto de trabajo se creará en una carpeta distinta, llamada `tel351-orq`.

Mantener la misma sesión durante la actividad. Las consultas a AWS utilizarán `sa-east-1` y las variables de shell obtenidas se reutilizarán en las etapas siguientes. No es necesario conservar la infraestructura de CLI ni CLF.

#### 1.2 Crear el proyecto CDK

1. Instalar la versión de AWS CDK CLI utilizada en la actividad e incorporarla al PATH de la sesión:

   ```bash
   npm install --global --prefix "$HOME/.local" --cache /tmp/tel351-orq-npm-cache aws-cdk@2.1146.1
   export PATH="$HOME/.local/bin:$PATH"
   export JSII_RUNTIME_PACKAGE_CACHE=disabled
   cdk --version
   ```

2. Crear una carpeta vacía e inicializar una aplicación CDK en Python:

   ```bash
   mkdir "$HOME/tel351-orq"
   cd "$HOME/tel351-orq"
   PIP_NO_CACHE_DIR=1 cdk init app --language python --lib-version 2.240.0
   ```

3. Esperar a que termine la inicialización y activar el entorno virtual generado:

   ```bash
   source .venv/bin/activate
   ```

`cdk init` genera `app.py`, `cdk.json`, `requirements.txt` y el paquete `tel351_orq`, que contiene un stack de ejemplo. También crea `.venv` e intenta instalar las dependencias de CDK. La opción `--lib-version` fija la versión de la biblioteca utilizada en el laboratorio, compatible con Python 3.9 y posteriores. La activación del entorno permite utilizar esas bibliotecas sin modificar las instaladas en el sistema. Las opciones de caché evitan ocupar innecesariamente el almacenamiento persistente limitado de CloudShell.

Desde este punto, ejecutar los comandos y editar los archivos dentro de **`$HOME/tel351-orq`**, no dentro de la copia del repositorio. AWS CLI, CDK y Boto3 utilizarán las credenciales temporales de CloudShell, sin configurar nuevas Access Keys.

#### 1.3 Incorporar los materiales al proyecto

La base proporcionada contiene los siguientes archivos:

| Archivo | Contenido |
| --- | --- |
| [`tel351_orq/tel351_orq_stack.py`](tel351_orq/tel351_orq_stack.py) | Infraestructura y dos ejercicios de referencias y permisos |
| [`functions/lambda_function.py`](functions/lambda_function.py) | Implementación completa de la API |
| [`data/stations.json`](data/stations.json) | Catálogo inicial de estaciones |
| [`scripts/initialize.py`](scripts/initialize.py) | Programa Boto3 con un ejercicio de escritura condicional |
| [`requirements.txt`](requirements.txt) | Dependencia adicional de Boto3 |

1. Copiar los materiales al proyecto de trabajo:

   ```bash
   cp "$HOME/courses-utfsm-tel351-orq/tel351_orq/tel351_orq_stack.py" tel351_orq/
   cp -R "$HOME/courses-utfsm-tel351-orq/functions" \
       "$HOME/courses-utfsm-tel351-orq/data" \
       "$HOME/courses-utfsm-tel351-orq/scripts" .
   cat "$HOME/courses-utfsm-tel351-orq/requirements.txt" >> requirements.txt
   python -m pip install --no-cache-dir -r requirements.txt
   ```

   La copia reemplaza el stack de ejemplo por el de la actividad. `app.py` y `cdk.json` se conservan; a las dependencias generadas se agrega Boto3. Comprobar que la instalación termine sin errores antes de continuar.

2. Abrir `app.py`:

   ```bash
   nano app.py
   ```

   Reemplazar solamente la llamada que crea `Tel351OrqStack` por el bloque siguiente:

   ```python
   Tel351OrqStack(
       app,
       "tel351-orq",
       env=cdk.Environment(
           account=os.environ["CDK_DEFAULT_ACCOUNT"],
           region="sa-east-1",
       ),
   )
   ```

   Conservar los imports, `app = cdk.App()` y `app.synth()`. La llamada asigna el nombre `tel351-orq` al stack y utiliza la cuenta de la sesión para desplegarlo en `sa-east-1`. No cambiar el nombre de la clase ni su import.

Guardar con **Ctrl+O**, confirmar con **Enter** y salir con **Ctrl+X**. Utilizar el mismo editor para los archivos de los ejercicios.

El código de la API está completo y no requiere implementar nuevamente sus operaciones. Los tres ejercicios están identificados mediante comentarios `EJERCICIO`. Conservar las partes proporcionadas y los nombres de variables indicados, ya que se utilizan en los bloques siguientes. En el programa Boto3, reemplazar `raise NotImplementedError(...)` por la implementación solicitada.

#### 1.4 Preparar el bootstrap

CDK utiliza un stack auxiliar llamado `CDKToolkit` para publicar archivos, como el código de Lambda, y disponer de los recursos de apoyo al despliegue. Esta preparación se realiza por combinación de cuenta y Región.

Obtener el account ID y ejecutar el bootstrap fuera de la carpeta del proyecto:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
(cd /tmp && cdk bootstrap "aws://$ACCOUNT_ID/sa-east-1")
```

Mientras se prepara el entorno, leer los dos ejercicios descritos en el apartado 2.1. No interrumpir el comando. Antes de editar el stack y ejecutar los comandos siguientes, comprobar que el bootstrap haya terminado correctamente. Si informa una falla, revisar **Events** de `CDKToolkit` en CloudFormation.

Si la cuenta y Región ya estaban preparadas, el comando podrá terminar sin cambios. `CDKToolkit` no es el stack `tel351-orq` que se desplegará durante la actividad.

### 2. Completar y desplegar la infraestructura

#### 2.1 Completar las referencias y los permisos

Abrir el archivo:

```bash
nano tel351_orq/tel351_orq_stack.py
```

La base declara una tabla con partition key `sectorId` y sort key `stationId`, ambas String, y capacidad bajo demanda. También incluye Lambda, su execution role, logs, la API y los outputs. Completar solamente los dos bloques indicados:

1. Agregar al diccionario `environment` la variable `TABLE_NAME`, obteniendo su valor desde la referencia `table`
2. Agregar a `execution_role` una policy con `dynamodb:Query` y `dynamodb:UpdateItem`, utilizando únicamente el ARN de esa tabla como recurso

No copiar nombres físicos ni ARN desde la consola. El apéndice muestra las propiedades de los constructs y un ejemplo de cómo agregar una policy.

Guardar los cambios. No cambiar las keys, los identificadores de los constructs ni las policies de eliminación proporcionadas.

#### 2.2 Sintetizar y desplegar

Ejecutar:

```bash
cdk synth
```

Identificar en el template generado la referencia utilizada para `TABLE_NAME` y la policy de acceso a DynamoDB. Si es necesario corregir algo, modificar `tel351_orq/tel351_orq_stack.py`, no los archivos generados dentro de `cdk.out`.

Ejecutar:

```bash
cdk deploy
```

Revisar los cambios de permisos antes de aprobar. Durante el despliegue, revisar desde el repositorio el catálogo y las operaciones descritas en el apartado 3.1. Esperar a que el comando termine y comprobar que `tel351-orq` alcance `CREATE_COMPLETE`. Si ocurre una falla, identificar su causa en **Events** de CloudFormation antes de corregir el proyecto. No crear manualmente los recursos para eludir un error de despliegue.

La base puede sintetizarse aunque falten los ejercicios. Sin embargo, consultar y actualizar estaciones requiere la referencia a la tabla y sus permisos; un despliegue exitoso no garantiza que esas operaciones funcionen.

#### 2.3 Descubrir el endpoint mediante AWS CLI

Construir una consulta con `aws cloudformation describe-stacks` para obtener el output `ApiUrl` de `tel351-orq` y asignar su valor a `API_URL`, utilizando `--query`, `--output text` y `$()`.

El apéndice incluye el patrón de consulta utilizado en CLF. Adaptar el nombre del stack y del output; no copiar manualmente la URL desde la consola.

Después de completar la asignación, comprobarla:

```bash
echo "$API_URL"
curl -sS "$API_URL/status"
```

La respuesta debe contener `status` igual a `operational` y `version` igual a `1.0`. La API está desplegada, pero todavía no tiene estaciones. Desde este momento se puede solicitar una evaluación parcial sin esperar a completar todas las etapas.

### 3. Inicializar las estaciones mediante Boto3

#### 3.1 Revisar el catálogo y las operaciones

Abrir `data/stations.json`. El catálogo contiene cuatro estaciones de dos sectores distintos: `core` y `outer-rim`. Cada estación tiene la estructura siguiente:

```json
{
  "sectorId": "core",
  "stationId": "coruscant-01",
  "name": "Coruscant Central",
  "status": "ACTIVE"
}
```

La combinación de `sectorId` y `stationId` identifica una estación. El archivo proporciona estados iniciales `ACTIVE`. Después de operar el sistema, los registros almacenados pueden tener estados diferentes, sin que esto signifique que el catálogo esté incompleto.

La API permite consultar y modificar esos registros:

| Operación | Resultado |
| --- | --- |
| `GET /status` | Estado del sistema y versión configurada |
| `GET /sectors/{sectorId}/stations` | Estaciones del sector, ordenadas por `stationId` |
| `PATCH /sectors/{sectorId}/stations/{stationId}` | Actualización del estado de una estación existente |

Las routes son públicas y se utilizan solamente con los datos del catálogo de esta actividad. No incorporar información personal ni reutilizar esta configuración sin autenticación para un sistema de producción.

La consulta responde con HTTP `200`, `sectorId` y un arreglo `stations`; para un sector sin estaciones, el arreglo está vacío. La actualización recibe solamente `status` y devuelve HTTP `200` con la estación actualizada. Un estado inválido produce HTTP `400` y una estación inexistente produce HTTP `404`, sin crear registros nuevos.

#### 3.2 Completar la carga inicial

Abrir el programa:

```bash
nano scripts/initialize.py
```

La función `discover_resources` está completa. Utiliza `describe_stacks` para obtener los outputs y construir un diccionario con sus nombres y valores. Desde ese diccionario obtiene el endpoint y el nombre de la tabla, sin incorporar identificadores físicos como valores fijos. Es la misma operación utilizada mediante AWS CLI, pero su respuesta se procesa como diccionarios y listas de Python.

En el **ejercicio 3**, dentro de `initialize_stations`, reemplazar `raise NotImplementedError(...)` por una llamada a `table.put_item` que escriba `station` solamente si no existe un item con la misma primary key.

La referencia a la tabla, el recorrido del catálogo, los contadores y el tratamiento de errores ya están preparados. Completar la llamada y su `ConditionExpression`, utilizando la referencia del apéndice. No eliminar el manejo de `ConditionalCheckFailedException`: permite continuar con las estaciones existentes sin ocultar otros errores.

Guardar el archivo y ejecutar desde la carpeta principal:

```bash
python scripts/initialize.py --stack-name tel351-orq
```

La primera ejecución sobre una tabla vacía debe informar cuatro estaciones creadas. Si una ejecución anterior alcanzó a escribir parte del catálogo, la siguiente debe incorporar solamente las estaciones restantes. La repetición de la inicialización se comprobará en el punto 4.3; no vaciar la tabla ni modificar el catálogo entre ejecuciones.

### 4. Comprobar la operación y la conservación del estado

#### 4.1 Consultar y actualizar una estación

Consultar las estaciones del sector `core`:

```bash
curl -sS "$API_URL/sectors/core/stations"
```

Repetir la consulta para el segundo sector indicado en el catálogo y comprobar que los resultados no se mezclen.

Cambiar el estado de `coruscant-01`:

```bash
curl -sS -i -X PATCH \
    "$API_URL/sectors/core/stations/coruscant-01" \
    -H 'Content-Type: application/json' \
    -d '{"status":"MAINTENANCE"}'
```

Consultar nuevamente el sector y comprobar que se conserve `MAINTENANCE`.

`-i` muestra los encabezados y el código HTTP junto con el body. Estas solicitudes utilizan la API del laboratorio. En cambio, el programa Boto3 utiliza directamente las APIs de CloudFormation y DynamoDB.

#### 4.2 Registrar el estado antes de repetir la preparación

1. Ingresar a [https://lab09.shareddomain.link](https://lab09.shareddomain.link)
2. Completar el account ID y el RUT normalizado
3. Seleccionar **Registrar comprobación inicial**, según lo descrito en **Evaluación**
4. Revisar los resultados y resolver las fallas de consulta o actualización que impidan registrar una estación como referencia
5. Esperar la confirmación del sitio antes de continuar

El evaluador utilizará la API para cambiar el estado de una estación del catálogo a un valor distinto de `ACTIVE` y registrará el resultado. Ese cambio representa una modificación realizada durante la operación del sistema.

#### 4.3 Repetir la inicialización

Ejecutar nuevamente:

```bash
python scripts/initialize.py --stack-name tel351-orq
```

La ejecución debe informar cero estaciones creadas y cuatro existentes. Seleccionar **Evaluar ahora** en el sitio y comprobar que el registro conserve su estado actual aunque el catálogo local indique `ACTIVE`. Si fue reemplazado, corregir la condición de escritura, solicitar una nueva comprobación inicial y repetir la secuencia. No restablecer manualmente el estado para intentar corregir el resultado de la prueba.

Revisar los resultados antes de terminar el bloque y corregir los aspectos pendientes. La infraestructura desplegada permite operar el sistema; el programa de inicialización incorpora los datos que faltan sin reemplazar los cambios realizados durante esa operación.

## Limpieza posterior

Realizar la limpieza después de terminar la evaluación, fuera de los 70 minutos de actividad. La eliminación de la tabla también eliminará las estaciones registradas.

1. Regresar a CloudShell en `sa-east-1`. Si se abrió una nueva sesión, recuperar el entorno del proyecto:

   ```bash
   cd "$HOME/tel351-orq"
   source .venv/bin/activate
   export PATH="$HOME/.local/bin:$PATH"
   export JSII_RUNTIME_PACKAGE_CACHE=disabled
   ```

2. Solicitar la eliminación del stack:

   ```bash
   cdk destroy
   ```

3. Revisar el nombre del stack y confirmar solamente la eliminación de `tel351-orq`
4. Seguir los eventos de CloudFormation hasta que termine la eliminación
5. Si aparece `DELETE_FAILED`, identificar el recurso y la causa informada antes de resolver el problema y repetir la eliminación
6. Comprobar que no permanezcan la API, la Lambda function, su execution role, la tabla ni el log group de la actividad

No eliminar `TEL351-Evaluator`, la identidad administrativa ni recursos de otros laboratorios. Conservar `CDKToolkit`, que puede utilizarse en otros despliegues CDK de la misma cuenta y Región. Este stack auxiliar y sus assets no forman parte de la eliminación de `tel351-orq`.

## Apéndice: Referencia de AWS CLI, CDK y Boto3

### Consultar los outputs mediante AWS CLI

La consulta `Stacks[0].Outputs` selecciona los outputs del stack. Para obtener el valor de un output específico, se puede seleccionar su `OutputKey` y conservar solamente `OutputValue`:

```bash
ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name mi-stack \
    --query "Stacks[0].Outputs[?OutputKey=='ServiceUrl'].OutputValue | [0]" \
    --output text)
```

En este ejemplo, reemplazar `mi-stack` y `ServiceUrl` por el stack y el output que se desea consultar. `$()` captura la salida del comando y `ENDPOINT=` la asigna a la variable; `--output text` devuelve el valor sin la estructura JSON. Para inspeccionar todos los outputs antes de seleccionar uno, utilizar `--query 'Stacks[0].Outputs' --output table`.

### Utilizar referencias entre constructs

Un construct expone propiedades que permiten configurar otros recursos sin conocer sus identificadores físicos. En esta actividad, `table.table_name` representa el nombre de la tabla y `table.table_arn` su ARN. CDK convierte esas referencias en expresiones del template, que CloudFormation resuelve durante el despliegue.

Una policy puede agregarse a un role mediante `add_to_policy`. Por ejemplo, para permitir que un role consulte el listado de un bucket S3:

```python
execution_role.add_to_policy(
    iam.PolicyStatement(
        actions=["s3:ListBucket"],
        resources=[bucket.bucket_arn],
    )
)
```

Adaptar las acciones y el recurso a las operaciones requeridas en DynamoDB. No utilizar `*` como recurso ni agregar permisos de escritura que la API no necesita.

### Escribir un item con una condición

La interfaz `resource` de DynamoDB permite trabajar con diccionarios Python sin declarar manualmente los tipos `S`, `N` o `BOOL` de cada atributo.

```python
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(table_name)

table.put_item(
    Item=item,
    ConditionExpression=condition,
)
```

`Item` contiene el registro que se desea guardar. `ConditionExpression` define una condición que DynamoDB comprueba antes de escribir. La función `attribute_not_exists(nombre)` permite comprobar la ausencia de un atributo en el item identificado por la primary key de la operación. Se pueden combinar condiciones mediante `AND`. Si la condición no se cumple, DynamoDB rechaza la escritura con `ConditionalCheckFailedException`.

Para una tabla con clave compuesta, DynamoDB identifica el item mediante la combinación de partition key y sort key. La condición se comprueba sobre ese item, no sobre todas las estaciones del sector.

El programa ya diferencia esa respuesta de otros errores. Una condición incumplida se contabiliza como una estación existente; una falla de permisos o de configuración se informa y detiene la ejecución. La condición debe acompañar a la escritura: una lectura previa seguida de una escritura sin condición no ofrece la misma protección.
