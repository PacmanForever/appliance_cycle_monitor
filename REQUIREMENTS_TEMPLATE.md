# Requisits de Home Activity Manager

## 1. Objectiu

Crear una integració local de Home Assistant per centralitzar en un únic dispositiu la configuració i la gestió de cada electrodomèstic no intel·ligent o bústia. La integració pot fer servir entitats que ja existeixen a Home Assistant com a fonts de dades, especialment un sensor de potència d'un endoll intel·ligent, però la detecció del cicle o de l'arribada de correu, l'estat, la configuració i les accions han de pertànyer al dispositiu gestionat per la integració.

L'usuari no ha de necessitar crear automatitzacions o blueprints externs per detectar l'inici o el final del cicle ni per executar les accions configurades.

Els tipus generals inicials són rentadora, rentaplats, assecadora, aire condicionat, nevera i bústia. Cada tipus ofereix les modalitats d'activitat que li corresponen: potència per als electrodomèstics de bugaderia; contacte de pala, potència o entitat `climate` per a l'aire condicionat; potència o interruptor per a la nevera; i moviment interior o contacte de portella per a la bústia. Les entrades auxiliars compatibles són independents de la modalitat. L'estructura ha de permetre afegir tipus futurs sense repartir condicions específiques per tipus entre els fluxos, el runtime i les plataformes d'entitats.

## 2. Identitat del projecte

- **Nom visible**: Home Activity Manager
- **Domini**: `home_activity_manager`
- **Tipus**: integració personalitzada de Home Assistant, distribuïble amb HACS
- **Funcionament**: local; sense API externa ni credencials
- **Font d'activitat**: una entitat de Home Assistant determinada per la modalitat seleccionada
- **Tipus generals inicials**: `washer`, `dishwasher`, `dryer`, `air_conditioner`, `refrigerator`, `mailbox`
- **Idioma font**: anglès
- **Idiomes de la interfície**: anglès, castellà i català

El domini es manté diferenciat de `appliance_cycle`, que ja fa servir una altra integració.

## 3. Gestió de dispositius

La integració ha de permetre:

- **Crear** un dispositiu per a cada electrodomèstic, amb nom i tipus propis.
- **Modificar** la configuració d'un dispositiu existent sense crear-ne un duplicat. El nom, les fonts, els valors i les accions s'han de poder canviar després de la configuració inicial, però el tipus general i la modalitat d'activitat són immutables; per canviar-los cal crear un dispositiu nou.
- **Eliminar** un dispositiu de la integració i retirar-ne les entitats del registre de Home Assistant quan ja no hi hagi cap entrada que les faci servir.
- Mantenir cada aparell i la seva configuració aïllats dels altres, encara que comparteixin la mateixa integració.
- Recuperar les entrades configurades després d'un reinici de Home Assistant.

Eliminar un dispositiu de la integració no ha d'esborrar entitats, helpers, temporitzadors ni scripts creats o gestionats per l'usuari.

## 4. Configuració de cada dispositiu

Cada dispositiu ha de tenir una configuració pròpia amb els camps següents.

### 4.1 Flux de configuració

La creació d'un dispositiu presenta cinc passos. En editar, el tipus i la modalitat existents es mostren fixos juntament amb el nom, i se segueix amb sensors, paràmetres i accions.

1. **Tipus i nom**: seleccionar el tipus general i definir-ne el nom.
2. **Modalitat d'activitat**: seleccionar la font d'activitat entre les disponibles per al tipus.
3. **Sensors**: seleccionar la font d'activitat obligatòria i les entrades compatibles.
4. **Paràmetres**: mostrar els llindars, temporitzacions i opcions aplicables.
5. **Accions**: mostrar els grups d'accions disponibles, que poden quedar buits.

Els passos segueixen la navegació estàndard cap endavant dels fluxos de Home Assistant; no cal afegir controls personalitzats per tornar a pantalles anteriors. En editar, es mostra la configuració desada. La validació s'ha de mostrar al pas corresponent abans de completar el flux. Cada perfil declara les seves fonts obligatòries i opcionals, paràmetres, grups d'accions i entitats de sortida.

Després de seleccionar el tipus i la modalitat, els passos de sensors, paràmetres i accions són independents per a cada perfil (combinació de tipus i modalitat). Cada perfil té identificadors de pas, formularis, camps, selectors i labels propis. No s'han de compartir pantalles, definicions de sensors ni labels entre perfils, encara que es repeteixin; una etiqueta opcional o obligatòria s'ha d'escriure directament al formulari de cada perfil i no derivar-se de condicions dinàmiques. Es pot reutilitzar lògica interna de validació o runtime sempre que no torni a unificar les definicions visibles dels formularis.

Aquest flux és el lloc central per configurar tot el comportament propi de l'electrodomèstic. Les automatitzacions externes no poden ser un requisit de funcionament. Es poden seleccionar entitats o accions ja existents a Home Assistant, inclosos scripts com a accions opcionals, però la integració ha de controlar directament la detecció de cicle i el moment d'execució de les accions.

### 4.2 Entitats d'entrada

- **Potència**: selector d'una entitat de potència de Home Assistant; obligatori en les modalitats per potència i opcional en les altres modalitats d'aparells endollats. Cal interpretar `W`/`kW` i ignorar lectures no vàlides sense fallar.
- **Energia**: selector opcional d'un sensor d'energia existent en aparells endollats. Si es selecciona, es mostra el seu total original en kWh; altrament, si hi ha potència, es calcula un total persistent. Les dues acumulacions són independents i canviar de font pot canviar el total visible; un sensor extern no disponible no provoca un canvi automàtic de font.
- **Contacte de pala de l'AC**: selector obligatori del perfil `air_conditioner_contact`. `on` significa AC en funcionament i `off` aturat; les transicions actualitzen l'estat de funcionament.
- **Obertura de porta de nevera**: selector obligatori dels perfils `refrigerator` i `refrigerator_switch`; reflecteix l'estat de porta i inicia o cancel·la l'alarma de porta oberta.
- **Switch de nevera**: al perfil `refrigerator`, selector opcional d'un endoll intel·ligent controlable que no altera la detecció per potència. Al perfil `refrigerator_switch`, el switch és obligatori, controla l'alimentació i és també la font binària d'activitat (`on` inicia i `off` finalitza el període).
- **Arribada de correu**: `mailbox_motion` requereix un sensor binari de moviment interior i `mailbox_slot` un sensor binari a la portella d'entrada. Una transició `off`→`on` després d'haver observat `off` indica una arribada; l'estat inicial `on` no ha de generar una arribada falsa.
- **Porta principal de la bústia**: selector obligatori dels dos perfils de bústia. L'obertura neteja «pendent de recollir» i cancel·la els recordatoris.
- **Obertura de porta per a bugaderia**: selector opcional per a rentadora, rentaplats i assecadora; activa estat de porta i «pendent de buidar».
- **Switch intel·ligent de l'endoll**: selector opcional en aparells endollats. La integració n'exposa el control; només determina l'activitat si és la font seleccionada.

Les fonts obligatòries depenen de la modalitat seleccionada. En AC poden coexistir contacte, potència i switch, però només la font seleccionada determina l'activitat. No es requereixen helpers externs: la integració proporciona les entitats de sortida de la secció 5. Les entitats seleccionades són fonts externes i no s'han d'esborrar quan s'elimina el dispositiu. La integració no n'ha de canviar mai l'associació amb un dispositiu pare; per mostrar-les al dispositiu de l'aparell, ha de crear o reutilitzar wrappers propis, llevat de l'excepció explícita de les entitats sense dispositiu pare descrita a la secció 5.

### 4.3 Detecció del cicle per potència

Tots els paràmetres de durada configurables s'expressen en segons. Els valors s'han de poder ajustar individualment per dispositiu, però no és obligatori modificar-los. La integració els aplica automàticament quan es crea el dispositiu. Els valors per defecte són els mostrats a les captures:

| Paràmetre | Valor inicial | Unitat | Comportament |
| --- | ---: | --- | --- |
| Llindar de potència d'inici | 4 | W | La potència ha de superar el llindar durant la histèresi d'inici per considerar que l'aparell ha començat. |
| Histèresi d'inici | 15 | s | Temps durant el qual la potència s'ha de mantenir per sobre del llindar d'inici. |
| Llindar de potència de finalització | 1 | W | La potència ha de baixar del llindar durant la histèresi de finalització per considerar que l'aparell ha acabat. |
| Histèresi de finalització | 60 | s | Temps durant el qual la potència s'ha de mantenir per sota del llindar de finalització. |
| Temps màxim de funcionament | buit | s | Opcional; buit desactiva l'avís de temps màxim. |

La configuració ha d'evitar canvis d'estat repetits per oscil·lacions breus de potència. Un cop iniciat un cicle, lectures entre els llindars d'inici i finalització no l'han de marcar com acabat. La validació ha d'impedir una configuració incoherent en què el llindar de finalització sigui igual o superior al d'inici.

Cada dispositiu pot tenir un **temps màxim de funcionament** configurable en segons. Si no s'especifica cap valor, aquesta protecció queda desactivada. El temps es compta des de l'inici confirmat del cicle. En superar-lo, la integració ha d'executar una sola vegada les accions de temps màxim configurades per a aquell cicle, si n'hi ha. La superació del límit no ha de marcar per si sola el cicle com a acabat ni apagar automàticament l'endoll; qualsevol apagada s'ha de configurar explícitament com una acció.

### 4.4 Perfils de tipus i comportaments addicionals

Els tipus s'han de definir en un registre de perfils extensible. Cada perfil declara fonts d'entrada, grups de paràmetres, grups d'accions, capacitats i entitats de sortida. Els fluxos i les plataformes han de derivar-ne els camps visibles; no han d'acumular condicions específiques disperses per nom de tipus. Els perfils de rentadora, rentaplats i assecadora es mantenen separats encara que facin servir avui els mateixos detectors i grups. Afegir un tipus nou que faci servir una estratègia existent ha de requerir registrar-ne el perfil i traduccions; només una estratègia nova requereix un detector nou.

- **Aire condicionat per contacte** (`air_conditioner_contact`): el contacte de pala és la font binària de funcionament. Les transicions `off`→`on` i `on`→`off` inicien i finalitzen respectivament el període actiu. La potència i l'energia són opcionals; no es creen «pendent de buidar» ni temps restant estimat.
- **Aire condicionat per potència** (`air_conditioner_power`): usa llindars/histèresi de potència per detectar activitat. No es creen «pendent de buidar» ni temps restant estimat.
- **Aire condicionat per entitat `climate`** (`air_conditioner_climate`): requereix una entitat `climate` existent sense dispositiu pare. L'entitat original s'associa directament al dispositiu creat per la integració, sense wrapper; conserva el seu identificador, la integració propietària i els controls. L'activitat segueix `hvac_action` quan existeix i, si no, l'estat de la climate. En substituir-la o eliminar l'entrada, torna a quedar sense dispositiu si encara està associada al dispositiu d'aquest aparell.
- **Nevera per potència** (`refrigerator`): requereix sensor de potència i contacte de porta. La potència detecta activitat del compressor i el contacte detecta l'obertura. Pot incloure opcionalment un switch intel·ligent controlable, que no canvia la detecció per potència. No s'hi creen «pendent de buidar» ni temps restant estimat. Hi ha dos grups independents d'alarma: porta oberta durant un temps configurable i compressor sense activitat durant un temps configurable.
- **Nevera per interruptor** (`refrigerator_switch`): requereix un interruptor intel·ligent que controla l'alimentació i és la font binària d'activitat; també requereix un contacte separat de porta. `on` inicia i `off` finalitza el període actiu. La potència i l'energia són opcionals; no es creen temps restant ni alarma de compressor inactiu. Manté l'alarma configurable de porta oberta.
- **Bústia amb moviment** (`mailbox_motion`): el moviment interior detecta l'arribada de correu. La porta principal és independent del sensor d'arribada i neteja l'estat pendent quan s'obre.
- **Bústia amb portella** (`mailbox_slot`): l'obertura de la portella d'entrada detecta l'arribada de correu. La porta principal és independent del contacte de portella i neteja l'estat pendent quan s'obre.
- En tots dos perfils de bústia, una arribada posa «pendent de recollir» a `on`, reinicia el recompte i activa les accions d'arribada. Els recordatoris configurats només s'inicien quan la porta principal consta tancada; si el correu arriba amb la porta oberta, es programen quan aquesta es tanca. El sensor d'arribada no s'interpreta com un inici o final de cicle.
- **Alarmes de nevera**: valors per defecte de 120 s amb la porta oberta, 3600 s sense compressor actiu, 900 s entre repeticions i 3 repeticions addicionals després del primer avís. S'executa l'acció inicial en complir-se el retard i després fins a N repeticions; les accions buides no fan res. Cada grup es rearma quan es resol la seva condició (porta tancada o compressor actiu) i manté el seu propi recompte.
- Els temporitzadors i recomptes d'alarmes es persisteixen i es restauren sense ràfegues després d'un reinici. Una transició `unknown`/`unavailable` no es considera resolució ni genera una alarma falsa.

### 4.5 Accions

Cada dispositiu pot tenir llistes d'accions de Home Assistant configurables i editables, compatibles amb les accions estàndard de Home Assistant. L'usuari ha de poder afegir, eliminar i reordenar diverses accions. Les llistes poden quedar buides sense impedir que el dispositiu detecti i mostri els cicles.

- **Accions en finalitzar el cicle**: grup general «Accions» de la captura. Exemples: enviar notificació, anunciar un missatge de veu i finalitzar un temporitzador.
- **Accions en iniciar el cicle**: s'executen quan se supera el llindar d'inici durant el temps d'histèresi. Exemples: enviar notificació, anunciar un missatge de veu i iniciar un temporitzador.
- **Accions en superar el temps màxim**: s'executen una sola vegada quan un cicle actiu supera el temps màxim configurat. Exemple: enviar una notificació. Aquest grup és independent de les accions de finalització.
- **Accions mentre està pendent de buidar**: grup opcional disponible quan s'ha configurat un sensor de porta. En finalitzar el cicle, si «pendent de buidar» continua `on`, s'espera l'interval configurat abans de la primera execució. Després es repeteixen cada X segons mentre la porta continuï tancada i no s'hagi assolit el màxim; cada interval de repetició es compta des que acaba l'execució anterior. L'interval X ha de ser un nombre enter positiu i el nombre màxim de repeticions un enter no negatiu; els valors per defecte són 900 segons (15 minuts) i 3 repeticions. El límit compta només les execucions posteriors a la inicial; amb 3 repeticions, hi ha com a màxim 4 execucions en total. En obrir-se la porta, l'estat es neteja i les accions pendents es cancel·len immediatament. En assolir el màxim, les repeticions s'aturen encara que la porta continuï tancada i «pendent de buidar» es manté `on` fins que s'obri.
- **Alarma d'endoll apagat**: disponible en qualsevol perfil que admeti un endoll intel·ligent seleccionat. En passar a `off`, executa immediatament les accions configurades i les repeteix cada interval propi mentre continuï apagat, fins al nombre màxim de repeticions. El valor per defecte de l'interval és 900 segons i el de repeticions addicionals és 3. En tornar a `on`, cancel·la el proper avís i rearma el recompte. Si la font queda temporalment no disponible, conserva l'estat i el venciment sense enviar avisos fins que es torni a confirmar `off`.
- **Alarma de porta de nevera**: acció pròpia del tipus nevera, disponible amb contacte configurat; s'executa després del retard de porta oberta i repeteix segons els paràmetres del perfil fins al màxim. Tancar la porta rearma el grup.
- **Alarma de compressor de nevera**: només al perfil `refrigerator`, que mesura potència; s'executa quan no s'ha detectat activitat del compressor durant el retard configurat i repeteix fins al màxim. Tornar a detectar activitat rearma el grup. No existeix al perfil `refrigerator_switch`.
- **Arribada de correu**: acció pròpia dels perfils de bústia, executada en detectar una arribada. Les accions de «pendent de recollir» segueixen el retard, interval i màxim de repeticions configurats, i es cancel·len en obrir-se la porta principal.

Les accions són configuració de cada dispositiu; no s'han de codificar com a scripts fixos ni compartir automàticament entre aparells. La integració les ha d'executar directament en l'ordre configurat quan detecti els canvis de cicle o de porta, sense dependre d'una automatització o blueprint extern. No s'han de solapar dues execucions del mateix grup. Es poden invocar scripts existents si l'usuari els selecciona, però no són obligatoris. Els errors d'una acció s'han de registrar sense interrompre la resta d'accions ni la detecció de cicles, i sense exposar dades sensibles.

## 5. Entitats i associació amb el dispositiu

- Cada electrodomèstic configurat ha d'aparèixer com un dispositiu propi al registre de dispositius de Home Assistant.
- Totes les entitats de sortida creades per la integració han d'estar associades al dispositiu de l'electrodomèstic i ser visibles des de la seva pàgina.
- **Regla d'associació i wrappers**: mai no s'han d'associar entitats externes seleccionades a un dispositiu creat per la integració. En tots els tipus d'aparell, cada entitat d'entrada configurada s'ha de representar al dispositiu mitjançant un wrapper propi de la integració; si ja hi ha una sortida equivalent que reflecteix aquesta font, s'ha de reutilitzar com a wrapper i no crear una segona entitat amb el mateix estat. L'única excepció són les entitats sense dispositiu pare indicades explícitament, com ara les entitats `climate` dels AC: aquestes s'assignen directament al dispositiu, sense wrapper, per conservar-ne els controls i la identitat originals. Si una entitat té un dispositiu pare, no se l'ha de reassignar.
- **Potència** i **Energia total consumida**: es creen segons les entrades configurades, independentment de la modalitat. L'energia es mostra en kWh, des d'un sensor extern o calculada i persistent a partir de potència.
- **Durada de l'últim període actiu**: sensor de sortida amb la durada del període d'activitat més recent detectat.
- **Temps restant estimat**: només es crea per perfils de cicle que en poden oferir una estimació útil. No es crea per AC ni nevera.
- **Estat (funcionament)**: entitat binària que indica si hi ha activitat segons l'estratègia declarada pel perfil.
- **Porta**: si el perfil usa un contacte de porta, entitat binària de sortida que en reflecteix l'estat.
- **Portella de bústia**: només per a `mailbox_slot`, entitat binària de sortida que reflecteix si el contacte de la portella d'arribada és obert o tancat. És diferent de l'entitat Porta, que representa l'obertura de la porta principal per recollir el correu.
- **Pendent de buidar/recollir**: per als perfils de bugaderia amb sensor de porta i per als perfils de bústia; mai per AC o nevera.
- **Neteja manual de l'estat pendent**: quan un dispositiu té un estat «pendent de buidar», la integració ha de crear-hi també un botó propi per posar-lo manualment a `off`, independentment dels sensors. Aquesta acció de recuperació ha de funcionar encara que el sensor associat falli o no estigui disponible, i ha de cancel·lar els recordatoris pendents i reiniciar-ne el recompte.
- **Endoll**: si el perfil admet un switch intel·ligent i se n'ha seleccionat un, entitat de switch associada que en reflecteix l'estat i permet activar-lo o desactivar-lo. Al perfil `refrigerator`, és opcional i no substitueix la detecció per potència; al perfil `refrigerator_switch`, és obligatori i també és la font de detecció d'activitat.
- **Entitats d'alarma**: les alarmes de nevera es representen amb els grups d'acció i els sensors d'estat declarats pel perfil; no es creen entitats de bugaderia per reaprofitar-les.
- Quan hi ha sensor d'obertura, «Pendent de buidar» passa a `on` en iniciar un cicle i es manté en acabar-lo, fins que el sensor físic indiqui que la porta s'ha obert; llavors passa a `off`. No s'ha de reiniciar només perquè el cicle hagi acabat. En una bústia, «Pendent de recollir» passa a `on` en detectar correu i a `off` en obrir la porta principal. Sense sensor d'obertura no es creen les entitats Porta ni Pendent.
- Un switch auxiliar a `off` no finalitza el període actiu; només ho fa quan el switch és la font d'activitat seleccionada.
- En iniciar un cicle, el temps restant estimat és la durada de l'últim cicle completat menys el temps transcorregut des de l'inici del cicle actual. S'ha d'actualitzar durant el cicle i no pot baixar de zero.
- Si encara no s'ha completat cap cicle, el temps restant estimat ha de ser desconegut/no disponible, no un valor inventat. L'estimació es basa només en l'últim cicle completat i s'ha d'identificar com a estimació, no com a mesura garantida.
- El sensor de potència i el sensor d'obertura seleccionats continuen sent les fonts de dades originals; les entitats de sortida i la gestió del cicle queden centralitzades al dispositiu de l'electrodomèstic.
- No s'han de crear helpers, scripts ni automatitzacions externes per representar estats o fer funcionar la lògica essencial de la integració.
- El nom i el tipus de cada aparell han de ser visibles i distingibles quan hi ha més d'un dispositiu configurat.
- Els identificadors d'entitat han de ser estables davant de canvis de llindars, accions o altres opcions.

## 6. Persistència i actualitzacions

- La configuració de dispositius, entitats vinculades, llindars, histèresis i accions s'ha de desar a les entrades de configuració de Home Assistant.
- La integració ha de persistir l'estat actiu del cicle, les marques temporals d'inici i dels temporitzadors d'histèresi, l'energia acumulada, la durada de l'últim cicle completat, l'estat «pendent de buidar», el nombre de repeticions ja executades i la data/hora prevista del proper avís.
- En reiniciar Home Assistant, s'ha de restaurar aquest estat i calcular els temps transcorreguts a partir de les marques temporals guardades; no s'han de reiniciar el cicle, el temps màxim, l'estimació de temps restant ni els intervals d'avís. Les accions d'inici del cicle ja executades no s'han de repetir.
- Després de restaurar, la integració ha de tornar a subscriure's a les entitats d'entrada i comprovar-ne l'estat actual. Si la porta és oberta, ha de netejar «pendent de buidar» i cancel·lar els avisos pendents. Si una entitat encara no està disponible, ha de conservar l'estat restaurat i esperar que torni a estar disponible, sense inferir una finalització.
- Si un avís de «pendent de buidar» ha vençut mentre Home Assistant era aturat i la porta continua tancada, es pot executar un únic avís de recuperació immediat; s'han d'ometre altres intervals vençuts sense enviar una ràfega i reprendre la cadència a partir del proper venciment futur. L'avís de recuperació compta dins del màxim configurat.
- El temps màxim configurat i l'estat d'avís ja executat del cicle actual s'han de conservar després d'un reinici, per evitar perdre el límit o repetir l'acció d'avís.
- Modificar una opció ha d'actualitzar només el dispositiu afectat i les seves entitats.
- La integració ha d'actualitzar-se davant de canvis de les entitats d'entrada sense fer sondeig de xarxa innecessari.
- Si una entitat seleccionada desapareix o queda no disponible, el dispositiu ha de continuar carregat i crear un issue de Repairs per a l'entitat. En recuperar-se, l'issue s'ha d'eliminar.

## 7. Seguretat i privadesa

- No es recullen ni s'envien dades a serveis externs.
- No es demanen credencials.
- Les accions només s'executen en resposta als canvis de cicle del dispositiu i segons la configuració de l'usuari.
- Els errors i registres no han d'incloure dades personals innecessàries.

## 8. Criteris d'acceptació

1. Es poden crear dos o més electrodomèstics i cadascun té dispositiu, valors i accions independents.
2. Es poden modificar i eliminar dispositius des de Home Assistant sense perdre ni esborrar entitats externes seleccionades.
3. Amb els valors inicials dels perfils de potència, l'activitat comença quan se supera 4 W durant 15 segons i acaba quan baixa d'1 W durant 60 segons; un switch auxiliar no altera el cicle.
4. Els valors de llindar i histèresi es poden editar per dispositiu i persisteixen després de reiniciar Home Assistant.
5. Les accions d'inici i de finalització s'executen separadament, en l'ordre configurat, i poden incloure notificacions, missatges de veu i operacions de temporitzador.
6. Els selectors d'entrada obligatòria i opcional corresponen al perfil triat; es pot crear un AC per contacte sense potència ni un AC per potència sense contacte.
7. El dispositiu exposa potència i energia segons les entrades seleccionades; no hi ha «Pendent de buidar» ni «Temps restant estimat» en AC o nevera.
8. Quan hi ha sensor d'obertura, «Pendent de buidar» passa a `on` en iniciar el cicle, es manté en acabar-lo i només torna a `off` quan s'obre la porta.
9. Cada dispositiu que tingui «Pendent de buidar» exposa un botó propi per posar l'estat a `off` manualment i cancel·lar els avisos, fins i tot si el sensor associat no està disponible.
10. L'energia calculada s'acumula durant la vida del dispositiu, es conserva després de reiniciar Home Assistant i torna a zero si es crea de nou; un sensor extern conserva i mostra el seu total original.
11. En iniciar un nou cicle després d'haver-ne completat un, el temps restant comença a partir de la durada de l'últim cicle i es redueix segons el temps transcorregut del cicle actual.
12. Abans de disposar d'un cicle completat, el temps restant és desconegut/no disponible; no es mostra una estimació fictícia.
13. Si Home Assistant es reinicia durant un cicle, l'estat de funcionament continua actiu, la durada i el temps restant es calculen des de les marques temporals originals i no es repeteixen les accions d'inici ja executades.
14. Una lectura de potència invàlida no provoca una fallada de la integració. Si una entitat d'entrada configurada falta o és `unknown`/`unavailable`, la integració continua carregada i crea un avís de Repairs per a aquella entitat; quan torna a estar disponible, elimina l'avís.
15. Els canvis breus de potència no generen inicis o finalitzacions falsos si no es compleix la histèresi corresponent.
16. Quan s'ha configurat un temps màxim, en superar-lo s'executen una sola vegada les accions específiques d'avís; el cicle no es dona per acabat ni l'endoll s'apaga automàticament.
17. Si hi ha accions de «pendent de buidar», la primera s'executa 900 segons (15 minuts) després de finalitzar el cicle, només si l'estat continua actiu; després es repeteixen cada X segons fins al màxim o fins que s'obre la porta.
18. El nombre màxim compta les repeticions posteriors a l'execució immediata inicial; amb el valor per defecte de 3, les accions s'executen com a màxim 4 vegades.
19. El retard inicial per defecte i l'interval per defecte entre repeticions són de 900 segons (15 minuts), modificables per dispositiu.
20. En assolir el màxim, les repeticions s'aturen però «pendent de buidar» continua actiu fins que s'obre la porta.
21. Si una acció periòdica dura més que l'interval configurat, no se solapa una segona execució del mateix grup; el següent interval comença quan acaba l'execució anterior. La finalització d'una acció de recordatori o alarma obsoleta no modifica l'estat ni els venciments d'una condició posterior.
22. Si Home Assistant es reinicia mentre «pendent de buidar» és actiu, l'estat i el nombre de repeticions es restauren; es respecta el proper venciment i, si ja ha passat, s'executa com a màxim un avís de recuperació sense superar el límit ni crear una ràfega.
23. Es pot completar la configuració amb nom, tipus i sensor de potència, sense sensor de porta ni switch, deixant el temps màxim i les accions buits i mantenint els llindars per defecte.
24. La creació mostra cinc passos: tipus/nom, modalitat, sensors, paràmetres i accions. En editar es mostren tipus i modalitat fixos amb el nom, seguits de sensors, paràmetres i accions.
25. Si es configura un switch intel·ligent, el seu estat es reflecteix i es pot controlar des de la pàgina del dispositiu; si no se'n configura cap, la integració funciona igualment sense crear aquesta entitat.
26. Un dispositiu funciona amb la seva configuració pròpia sense que l'usuari hagi de crear automatitzacions, blueprints o helpers externs per detectar cicles, representar-ne l'estat o executar les accions.
27. Una acció fallida no impedeix executar les accions posteriors ni altera la detecció del cicle.
28. Tots els textos visibles de la interfície tenen traducció completa en anglès, castellà i català.
29. Les propostes de nova icona són `docs/home_activity_manager_icon_option_1.svg` i `docs/home_activity_manager_icon_option_2.svg`. Cal escollir-ne una abans de substituir la icona de marca actual.
30. Les modalitats d'AC requereixen la font seleccionada i admeten contacte, potència i switch auxiliars.
31. Els perfils d'AC no creen «Pendent de buidar» ni «Temps restant estimat»; potència i energia depenen de les entrades seleccionades.
32. La nevera per potència (`refrigerator`) exigeix potència i contacte de porta, admet un switch de control opcional sense substituir la detecció per potència, crea estat de funcionament i porta, no crea «Pendent de buidar» ni temps restant, i ofereix alarmes independents de porta oberta i compressor inactiu.
33. Les alarmes de nevera permeten un avís inicial més N repeticions addicionals; tancar la porta o reprendre l'activitat del compressor rearma només el grup corresponent.
34. Rentadora, rentaplats i assecadora tenen perfils separats encara que comparteixin capacitats. Un perfil futur pot declarar paràmetres i accions diferents sense afegir condicions duplicades a cada capa.
35. Es poden configurar els perfils `mailbox_motion` i `mailbox_slot` amb el seu sensor d'arribada i un contacte separat per a la porta principal.
36. Després d'observar el sensor d'arribada apagat, cada transició a `on` executa les accions d'arribada i activa «Pendent de recollir»; l'estat inicial `on` o un estat no disponible no genera una arribada falsa.
37. Obrir la porta principal neteja «Pendent de recollir» i cancel·la recordatoris. Si arriba correu amb la porta oberta, l'estat queda pendent però els recordatoris esperen que la porta es tanqui.
38. La nevera per interruptor (`refrigerator_switch`) exigeix switch i contacte de porta; el switch és la font d'activitat. Pot mostrar potència i energia auxiliars, i ofereix alarma de porta oberta però no de compressor inactiu. El switch auxiliar de `refrigerator` no finalitza per si sol el període actiu.
39. En editar una entrada existent, el tipus i la modalitat es mostren però no es poden canviar; el nom, les fonts, els paràmetres i les accions es poden editar. Per canviar-los cal crear una entrada nova.
40. En crear o editar un perfil de bústia, el sensor d'arribada i el contacte de la porta principal han de ser entitats diferents; si se selecciona la mateixa entitat, el flux mostra un error i no desa la configuració.
41. El perfil `mailbox_slot` exposa l'estat obert/tancat del contacte de portella com una entitat «Portella» separada de «Porta». El perfil `mailbox_motion` no crea aquesta entitat.
42. Tots els perfils que admeten un endoll intel·ligent exposen, quan n'hi ha un de seleccionat, un grup d'accions i paràmetres independents per a l'endoll apagat. El primer avís és immediat, se'n poden configurar N repeticions addicionals, no s'envien repeticions després de `on` i l'estat, recompte i venciment es restauren després d'un reinici.
43. Cada categoria té un pas de modalitat i opcions de traducció propis; cada perfil té identificadors de pas, formularis de sensors, paràmetres i accions, i labels de traducció independents. Les proves han de recórrer totes les categories i perfils i confirmar que els formularis i les claus de traducció estan aïllats, inclosa la indicació explícita «(optional)» o «(opcional)» als camps opcionals.

## 9. Qualitat i proves

- La suite ha d'incloure proves unitàries i proves de component de Home Assistant, amb fixtures i dades de prova deterministes. Les proves no han de dependre de dispositius reals ni de serveis externs.
- La cobertura combinada de codi de la integració, calculada a partir de les proves unitàries i de component juntes, ha de ser **com a mínim del 95%**. Un únic check de cobertura agregada ha d'executar o combinar ambdues suites i aplicar `--cov-fail-under=95`; no s'exigeix que cada suite individual assoleixi el 95%. Una cobertura combinada inferior ha de fer fallar el check.
- Les proves han de cobrir com a mínim els passos de creació i edició, cada perfil, fonts i selectors condicionals, estratègies d'activitat, grups d'accions específics, alarmes de nevera, arribades de bústia, entitats condicionals i els casos de cicle, recordatoris, energia i edició.
- Cada perfil ha de tenir proves unitàries dels seus selectors, paràmetres, accions i entitats declarades, i proves de component que completin el cicle CRUD de l'entrada: crear, llegir, editar i eliminar.
- Abans d'integrar canvis a `main` o publicar una versió, tots els checks obligatoris han de passar. Els checks s'han de configurar com a requerits per a les branques protegides de GitHub.

## 10. GitHub Actions i compatibilitat

El repositori ha de tenir workflows independents per als tests unitaris, els tests de component, la validació HACS, la validació Hassfest i la compatibilitat diària:

- **Tests unitaris**: executar la suite unitària i publicar-ne les dades de cobertura per a l'agregador.
- **Tests de component**: executar la integració dins de Home Assistant i publicar-ne les dades de cobertura per a l'agregador.
- **Cobertura agregada**: combinar els resultats unitaris i de component i exigir un mínim del 95% sobre el codi de la integració.
- **Validació HACS**: executar `hacs/action` amb la categoria `integration`.
- **Validació Hassfest**: executar l'acció oficial `home-assistant/actions/hassfest`.
- **Compatibilitat diària**: cada dia a les 06:00 UTC, instal·lar la darrera versió estable disponible de Home Assistant i executar-hi els tests de component. No s'ha de fixar aquesta execució diària a una versió antiga concreta. El workflow també ha de permetre execució manual.
- Els workflows de tests i validació s'han d'executar en `push` a `main`, en `pull_request` cap a `main` i amb `workflow_dispatch`. El workflow diari ha de tenir el disparador `schedule` i `workflow_dispatch`.
- Els errors de validació, tests o cobertura han de deixar el check de GitHub en fallada i impedir la integració o publicació fins que es resolguin.

## 11. GitHub, HACS i publicacions

- El repositori de codi ha de ser públic i tenir documentació d'instal·lació, configuració, entitats, ús, limitacions i suport.
- L'estructura ha de seguir el format d'integració HACS: `custom_components/home_activity_manager/`, manifest vàlid, configuració HACS de categoria `integration`, fitxers de traducció i metadades necessaris per a Home Assistant.
- Abans de cada publicació, han de passar HACS validation, Hassfest, tests i cobertura. El README ha d'incloure badges d'estat dels workflows i de cobertura.
- Les versions han de seguir Semantic Versioning. Els tags Git i els noms de les releases de GitHub han de fer servir el format `vX.Y.Z` (per exemple, `v1.2.3`); la versió numèrica del manifest ha de coincidir amb el tag i la release. Cada release ha d'actualitzar el changelog amb el mateix format.
- La submissió al repositori per defecte de HACS és un pas de publicació separat: preparar-la i demanar-ne la inclusió quan el repositori i la primera release compleixin els requisits de HACS.

## 12. Idiomes i marca

- L'anglès és l'idioma font per a les cadenes de la interfície i la documentació principal del projecte.
- Tots els textos visibles a Home Assistant han de fer servir claus de traducció; no s'han de codificar directament dins la lògica de la integració.
- La interfície ha de tenir traduccions completes en anglès, castellà (`es`) i català (`ca`), inclosos els passos de configuració, tipus, modalitats, noms i estats de les entitats, opcions, validacions i errors.
- Les traduccions han de mantenir el mateix conjunt de claus i significat. Les proves o validacions han de detectar claus absents o sobrants.
- La icona anterior `docs/appliance_cycle_monitor_icon.svg` es conserva com a referència de la marca antiga. Les noves propostes són `docs/home_activity_manager_icon_option_1.svg` (casa i òrbita d'activitat) i `docs/home_activity_manager_icon_option_2.svg` (casa i pols d'activitat); l'usuari n'ha d'escollir una abans d'actualitzar els recursos finals de marca.
- La icona escollida ha de ser llegible a mida petita i sobre fons clars i foscos, i representar activitat domèstica de manera genèrica sense identificar-se només amb un tipus de dispositiu.

## 13. Estat del model i evolució futura

### Tipus generals, modalitats i capacitats

**Estat: implementat a la versió 0.8.0 per als tipus i modalitats actuals.** No s'afegeix, de moment, un tipus de dispositiu personalitzat.

El tipus general, la modalitat que determina l'activitat i les capacitats opcionals són conceptes separats. Els perfils interns fan servir els detectors existents sense perdre les funcions específiques de cada aparell.

El tipus general i la modalitat són fixos després de la creació i han de ser identificables a la interfície. Es pot substituir l'entitat font per una altra compatible amb la mateixa modalitat; una font `climate` no es pot deixar buida en desar, i cal substituir-la o eliminar l'aparell.

La creació segueix cinc passos:

1. **Tipus i nom**: seleccionar el tipus general i donar nom a l'aparell.
2. **Modalitat d'activitat**: triar una modalitat obligatòria entre les compatibles amb el tipus seleccionat.
3. **Fonts i controls**: seleccionar obligatòriament l'entitat corresponent a la modalitat i, opcionalment, les altres fonts i controls compatibles. Si el tipus necessita altres entrades per a una funció concreta, cal definir-ne l'obligatorietat per separat.
4. **Paràmetres**: mostrar només els llindars, temporitzacions i opcions aplicables a les fonts i funcions configurades.
5. **Accions**: mostrar les accions disponibles per a les funcions configurades.

- La modalitat escollida determina quina font mana sobre l'activitat. Els altres sensors poden proporcionar mesures, estats, alarmes o control, però no han d'alterar l'activitat. No s'intenta endevinar si l'usuari ha triat el sensor físic correcte.
- Exemple d'AC: el contacte de pala, el sensor de potència, el sensor d'energia i l'interruptor poden coexistir. Només la modalitat escollida determina l'activitat; les altres entrades serveixen per mesurar, mostrar o controlar. Una entitat `climate` conserva els controls originals.
- Si la modalitat és l'interruptor, el seu estat determina l'activitat encara que la potència indiqui un altre valor. Si la modalitat és potència, l'interruptor auxiliar no finalitza ni impedeix un cicle.
- En aparells endollats, el control per interruptor, la potència instantània i l'energia acumulada són capacitats independents de la modalitat. L'energia existent mostra el seu total en kWh; si no se selecciona, es calcula a partir de la potència quan n'hi ha. El total calculat es manté separat del total extern.
- Si la font obligatòria queda `unknown` o `unavailable`, no se substitueix automàticament per una altra ni es provoca una transició falsa. Cada modalitat té una sola font d'activitat seleccionada; no es combinen fonts per decidir l'estat.

### Modalitats i capacitats implementades

| Tipus general | Modalitats actuals que es poden agrupar | Funcions i límits a conservar |
| --- | --- | --- |
| Rentadora, rentaplats i assecadora | Potència, actualment una per cada tipus | Cicle, temps màxim i estimació; porta i pendent de buidar opcionals. Altres modalitats són una extensió a definir, no una capacitat actual. |
| Aire condicionat | Contacte de pala, potència o `climate` | Una sola font d'activitat; contacte, potència, energia i interruptor poden coexistir. La `climate` original conserva associació i controls, sense wrapper. |
| Nevera | Potència o interruptor | Contacte i alarma de porta; potència i energia auxiliars són compatibles amb la modalitat d'interruptor. L'alarma de compressor inactiu només existeix en modalitat de potència. |
| Bústia | Moviment interior o contacte de portella | La modalitat detecta una arribada com a esdeveniment, no un estat de funcionament continu. Cal mantenir la porta principal separada, el pendent de recollir, les accions i els recordatoris. |
| Tendall o persiana, futurs | Pendent d'investigació | Cal decidir si es detecta moviment, posició o estat obert/tancat, i com es controla l'aparell, inclosa una possible entitat `cover`. Una posició oberta no implica que el motor estigui funcionant. |

Els detectors i les sortides no són intercanviables: cal conservar la semàntica de cada modalitat. La compatibilitat de dispositius futurs requerirà definir-ne els estats, esdeveniments i controls; també caldrà estudiar si un dispositiu que només agrupa entitats necessita una modalitat d'activitat obligatòria.

### Decisions aplicades

- La potència es mesura independentment de l'activitat. L'energia externa mostra el total original; el total calculat es manté separat. Canviar de font pot canviar el total visible i un sensor extern indisponible no provoca una substitució automàtica.
- Cada tipus declara les modalitats permeses, les entrades obligatòries i opcionals, les capacitats, les alarmes i les accions. Un interruptor encès indica alimentació, no necessàriament activitat del compressor; per això no activa una alarma de compressor inactiu.
- El projecte està en proves: s'accepten canvis incompatibles i començar de zero; no és obligatòria una migració automàtica de les configuracions existents.
- En substituir la font durant un cicle, se'n conserva l'inici i es finalitza quan la nova font confirma que està aturada; la potència respecta la histèresi i una font indisponible no força una transició. En substituir una `climate`, s'allibera l'anterior sense modificar altres associacions.

### Altres decisions pendents

- Definir límits mínims i màxims dels controls numèrics; els valors inicials sí que queden fixats en aquest document.
- Documentar i revisar les versions mínimes de Home Assistant i Python suportades.
- Investigar l'ampliació de l'abast a dispositius com tendalls i persianes, i a altres dispositius no intel·ligents que es vulguin automatitzar o simplement agrupar sota un únic dispositiu de Home Assistant. Valorar com una sola integració podria reunir-ne diverses funcionalitats i facilitar la descoberta, configuració i ús de les entitats a Home Assistant.

**Data d'actualització**: 2026-10-29