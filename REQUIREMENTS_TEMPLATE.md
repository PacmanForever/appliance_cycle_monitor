# Requisits de Appliance Cycle Monitor

## 1. Objectiu

Crear una integració local de Home Assistant per centralitzar en un únic dispositiu la configuració i la gestió de cada electrodomèstic no intel·ligent. La integració pot utilitzar entitats que ja existeixen a Home Assistant com a fonts de dades, especialment un sensor de potència d'un endoll intel·ligent, però la detecció del cicle, l'estat, la configuració i les accions han de pertànyer al dispositiu gestionat per la integració.

L'usuari no ha de necessitar crear automatitzacions o blueprints externs per detectar l'inici o el final del cicle ni per executar les accions configurades.

Els primers tipus previstos són rentadora, rentaplats i assecadora. L'estructura ha de permetre afegir altres aparells que segueixin cicles d'ús semblants.

## 2. Identitat del projecte

- **Nom visible**: Appliance Cycle Monitor
- **Domini proposat**: `appliance_cycle_monitor`
- **Tipus**: integració personalitzada de Home Assistant, distribuïble amb HACS
- **Funcionament**: local; sense API externa ni credencials
- **Font de dades principal**: entitat de potència de Home Assistant
- **Tipus de dispositiu inicials**: `washer`, `dishwasher`, `dryer`
- **Idioma font**: anglès
- **Idiomes de la interfície**: anglès, castellà i català

El domini es manté diferenciat de `appliance_cycle`, que ja l'utilitza una altra integració.

## 3. Gestió de dispositius

La integració ha de permetre:

- **Crear** un dispositiu per a cada electrodomèstic, amb nom i tipus propis.
- **Modificar** la configuració d'un dispositiu existent sense crear-ne un duplicat. Els valors i accions s'han de poder canviar després de la configuració inicial.
- **Eliminar** un dispositiu de la integració i retirar-ne les entitats del registre de Home Assistant quan ja no hi hagi cap entrada que les utilitzi.
- Mantenir cada aparell i la seva configuració aïllats dels altres, encara que comparteixin la mateixa integració.
- Recuperar les entrades configurades després d'un reinici de Home Assistant.

Eliminar un dispositiu de la integració no ha d'esborrar entitats, helpers, temporitzadors ni scripts creats o gestionats per l'usuari.

## 4. Configuració de cada dispositiu

Cada dispositiu ha de tenir una configuració pròpia amb els camps següents.

### 4.1 Flux de configuració en tres pantalles

La creació i l'edició d'un dispositiu han de presentar exactament aquests tres passos, en aquest ordre:

1. **Sensors i entitats**: seleccionar el sensor de potència obligatori i, opcionalment, el sensor d'obertura de porta i el switch intel·ligent de l'endoll. També es defineixen el nom i el tipus de l'electrodomèstic. L'estat de funcionament, l'estat de porta i «pendent de buidar» són entitats pròpies de la integració quan se'n compleixen les condicions.
2. **Temps i potències**: mostrar valors per defecte per als llindars i les histèresis d'inici/finalització, i permetre configurar opcionalment el temps màxim de funcionament. Els valors tenen unitats visibles i no cal modificar-los per completar la configuració.
3. **Accions**: permetre configurar opcionalment accions d'inici de cicle, finalització de cicle, superació del temps màxim i estat «pendent de buidar». Per a aquest darrer grup també es configuren l'interval en segons i el nombre màxim de repeticions. Tots els grups poden quedar buits.

Els passos segueixen la navegació estàndard cap endavant dels fluxos de Home Assistant; no cal afegir controls personalitzats per tornar a pantalles anteriors. En editar un dispositiu, les tres pantalles han d'aparèixer amb la configuració desada. Només el sensor de potència és obligatori entre les entitats i valors de funcionament; el nom i el tipus són obligatoris per identificar el dispositiu. La validació s'ha de mostrar al pas corresponent abans de completar el flux.

Aquest flux és el lloc central per configurar tot el comportament propi de l'electrodomèstic. Les automatitzacions externes no poden ser un requisit de funcionament. Es poden seleccionar entitats o accions ja existents a Home Assistant, inclosos scripts com a accions opcionals, però la integració ha de controlar directament la detecció de cicle i el moment d'execució de les accions.

### 4.2 Entitats d'entrada

- **Sensor de potència**: selector obligatori d'una entitat de potència de Home Assistant. La integració ha d'interpretar-ne correctament la unitat (`W` o `kW`) i ignorar lectures `unknown`, `unavailable` o no numèriques sense fallar.
- **Sensor d'obertura de porta**: selector opcional d'una entitat binària de Home Assistant. Quan es configura i indica que la porta és oberta, la integració ha d'actualitzar l'estat de porta del dispositiu i posar «pendent de buidar» a `off`.
- **Switch intel·ligent de l'endoll**: selector opcional d'una entitat `switch` de Home Assistant. Quan es configura, la integració n'ha d'exposar el control al dispositiu de l'electrodomèstic.

El sensor de potència és l'única entitat d'entrada obligatòria. El sensor de porta i el switch intel·ligent són opcionals. No s'ha de requerir que l'usuari creï o seleccioni entitats auxiliars d'estat o un `input_boolean`: la integració proporciona les entitats de gestió descrites a la secció 5. Les entitats seleccionades són fonts externes i no s'han d'esborrar quan s'elimina el dispositiu de la integració.

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

### 4.4 Accions

Cada dispositiu pot tenir llistes d'accions de Home Assistant configurables i editables, compatibles amb les accions estàndard de Home Assistant. L'usuari ha de poder afegir, eliminar i reordenar diverses accions. Les llistes poden quedar buides sense impedir que el dispositiu detecti i mostri els cicles.

- **Accions en finalitzar el cicle**: grup general «Accions» de la captura. Exemples: enviar notificació, anunciar un missatge de veu i finalitzar un temporitzador.
- **Accions en iniciar el cicle**: s'executen quan se supera el llindar d'inici durant el temps d'histèresi. Exemples: enviar notificació, anunciar un missatge de veu i iniciar un temporitzador.
- **Accions en superar el temps màxim**: s'executen una sola vegada quan un cicle actiu supera el temps màxim configurat. Exemple: enviar una notificació. Aquest grup és independent de les accions de finalització.
- **Accions mentre està pendent de buidar**: grup opcional disponible quan s'ha configurat un sensor de porta. En finalitzar el cicle, si «pendent de buidar» continua `on`, s'espera l'interval configurat abans de la primera execució. Després es repeteixen cada X segons mentre la porta continuï tancada i no s'hagi assolit el màxim. L'interval X ha de ser un nombre enter positiu i el nombre màxim de repeticions un enter no negatiu; els valors per defecte són 900 segons (15 minuts) i 3 repeticions. El límit compta només les execucions posteriors a la inicial; amb 3 repeticions, hi ha com a màxim 4 execucions en total. En obrir-se la porta, l'estat es neteja i les accions pendents es cancel·len immediatament. En assolir el màxim, les repeticions s'aturen encara que la porta continuï tancada i «pendent de buidar» es manté `on` fins que s'obri.

Les accions són configuració de cada dispositiu; no s'han de codificar com a scripts fixos ni compartir automàticament entre aparells. La integració les ha d'executar directament en l'ordre configurat quan detecti els canvis de cicle o de porta, sense dependre d'una automatització o blueprint extern. No s'han de solapar dues execucions del mateix grup si una acció triga més que l'interval configurat. Es poden invocar scripts existents si l'usuari els selecciona, però no són obligatoris. Els errors d'una acció s'han de registrar sense interrompre la resta d'accions ni la detecció de cicles, i sense exposar dades sensibles.

## 5. Entitats i associació amb el dispositiu

- Cada electrodomèstic configurat ha d'aparèixer com un dispositiu propi al registre de dispositius de Home Assistant.
- Totes les entitats de sortida creades per la integració han d'estar associades al dispositiu de l'electrodomèstic i ser visibles des de la seva pàgina.
- **Potència**: sensor de sortida en watts, actualitzat a partir de l'entitat d'entrada seleccionada.
- **Energia total consumida**: sensor acumulat en kWh durant tota la vida de la configuració del dispositiu, calculat a partir de la potència mesurada i persistent després de reiniciar Home Assistant. En eliminar el dispositiu, el total s'elimina; si es crea de nou, comença a zero.
- **Durada de l'últim cicle**: sensor de sortida amb la durada real del cicle completat més recent, calculada entre l'inici i la finalització detectats.
- **Temps restant estimat**: sensor de sortida amb el temps estimat fins al final del cicle actual, calculat a partir de la durada de l'últim cicle completat.
- **Estat (funcionament)**: entitat binària que indica si la integració considera que hi ha un cicle en marxa.
- **Porta**: si s'ha seleccionat un sensor d'obertura, entitat binària de sortida que reflecteix el seu estat.
- **Pendent de buidar**: si s'ha seleccionat un sensor d'obertura, entitat binària pròpia del dispositiu, gestionada automàticament, no un `input_boolean` ni un helper extern.
- **Neteja manual de l'estat pendent**: quan un dispositiu té un estat «pendent de buidar», la integració ha de crear-hi també un botó propi per posar-lo manualment a `off`, independentment dels sensors. Aquesta acció de recuperació ha de funcionar encara que el sensor associat falli o no estigui disponible, i ha de cancel·lar els recordatoris pendents i reiniciar-ne el recompte.
- **Endoll**: si s'ha seleccionat un switch intel·ligent, entitat de switch associada al dispositiu de l'electrodomèstic que reflecteix el seu estat i permet activar-lo o desactivar-lo.
- Quan hi ha sensor d'obertura, «Pendent de buidar» passa a `on` en iniciar un cicle i es manté en acabar-lo, fins que el sensor físic indiqui que la porta s'ha obert; llavors passa a `off`. No s'ha de reiniciar només perquè el cicle hagi acabat. Sense sensor d'obertura no es creen les entitats Porta ni Pendent de buidar.
- Si el dispositiu té un switch seleccionat i aquest passa a `off` mentre hi ha un cicle actiu, la integració ha de donar el cicle per finalitzat en aquell moment i executar les accions de finalització. No ha d'esperar la histèresi de potència; si el canvi a `off` també fa baixar la potència, només s'ha de registrar una finalització. L'aturada del switch no ha d'apagar ni modificar cap dispositiu extern addicional.
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
- Si una entitat seleccionada desapareix o queda no disponible, el dispositiu ha de continuar carregat i registrar un avís recuperable.

## 7. Seguretat i privadesa

- No es recullen ni s'envien dades a serveis externs.
- No es demanen credencials.
- Les accions només s'executen en resposta als canvis de cicle del dispositiu i segons la configuració de l'usuari.
- Els errors i registres no han d'incloure dades personals innecessàries.

## 8. Criteris d'acceptació

1. Es poden crear dos o més electrodomèstics i cadascun té dispositiu, valors i accions independents.
2. Es poden modificar i eliminar dispositius des de Home Assistant sense perdre ni esborrar entitats externes seleccionades.
3. Amb els valors inicials, el cicle comença quan la potència supera 4 W durant 15 segons i acaba quan baixa de 1 W durant 60 segons, tret que el switch seleccionat passi a `off` durant el cicle; en aquest cas, acaba immediatament.
4. Els valors de llindar i histèresi es poden editar per dispositiu i persisteixen després de reiniciar Home Assistant.
5. Les accions d'inici i de finalització s'executen separadament, en l'ordre configurat, i poden incloure notificacions, missatges de veu i operacions de temporitzador.
6. El dispositiu es pot crear amb només el sensor de potència; l'obertura de porta i el switch són opcionals.
7. El dispositiu exposa Potència, Energia total consumida, Durada de l'últim cicle, Temps restant estimat i Estat (funcionament). Porta i Pendent de buidar només es creen si s'ha configurat una entrada d'obertura; Endoll només es crea si s'ha configurat un switch.
8. Quan hi ha sensor d'obertura, «Pendent de buidar» passa a `on` en iniciar el cicle, es manté en acabar-lo i només torna a `off` quan s'obre la porta.
9. Cada dispositiu que tingui «Pendent de buidar» exposa un botó propi per posar l'estat a `off` manualment i cancel·lar els avisos, fins i tot si el sensor associat no està disponible.
10. L'energia consumida s'acumula durant la vida del dispositiu, es conserva després de reiniciar Home Assistant i torna a zero si s'elimina i es crea de nou el dispositiu.
11. En iniciar un nou cicle després d'haver-ne completat un, el temps restant comença a partir de la durada de l'últim cicle i es redueix segons el temps transcorregut del cicle actual.
12. Abans de disposar d'un cicle completat, el temps restant és desconegut/no disponible; no es mostra una estimació fictícia.
13. Si Home Assistant es reinicia durant un cicle, l'estat de funcionament continua actiu, la durada i el temps restant es calculen des de les marques temporals originals i no es repeteixen les accions d'inici ja executades.
14. Una lectura de potència invàlida o una entitat d'entrada no disponible no provoca una fallada de la integració.
15. Els canvis breus de potència no generen inicis o finalitzacions falsos si no es compleix la histèresi corresponent.
16. Quan s'ha configurat un temps màxim, en superar-lo s'executen una sola vegada les accions específiques d'avís; el cicle no es dona per acabat ni l'endoll s'apaga automàticament.
17. Si hi ha accions de «pendent de buidar», la primera s'executa 900 segons (15 minuts) després de finalitzar el cicle, només si l'estat continua actiu; després es repeteixen cada X segons fins al màxim o fins que s'obre la porta.
18. El nombre màxim compta les repeticions posteriors a l'execució immediata inicial; amb el valor per defecte de 3, les accions s'executen com a màxim 4 vegades.
19. El retard inicial per defecte i l'interval per defecte entre repeticions són de 900 segons (15 minuts), modificables per dispositiu.
20. En assolir el màxim, les repeticions s'aturen però «pendent de buidar» continua actiu fins que s'obre la porta.
21. Si una acció periòdica dura més que X segons, no s'inicia una segona execució del mateix grup fins que acabi la primera.
22. Si Home Assistant es reinicia mentre «pendent de buidar» és actiu, l'estat i el nombre de repeticions es restauren; es respecta el proper venciment i, si ja ha passat, s'executa com a màxim un avís de recuperació sense superar el límit ni crear una ràfega.
23. Es pot completar la configuració amb nom, tipus i sensor de potència, sense sensor de porta ni switch, deixant el temps màxim i les accions buits i mantenint els llindars per defecte.
24. La creació i l'edició mostren exactament tres pantalles en l'ordre definit: sensors/entitats, temps/potències i accions d'inici/finalització/temps màxim/pendent de buidar.
25. Si es configura un switch intel·ligent, el seu estat es reflecteix i es pot controlar des de la pàgina del dispositiu; si no se'n configura cap, la integració funciona igualment sense crear aquesta entitat.
26. Un dispositiu funciona amb la seva configuració pròpia sense que l'usuari hagi de crear automatitzacions, blueprints o helpers externs per detectar cicles, representar-ne l'estat o executar les accions.
27. Una acció fallida no impedeix executar les accions posteriors ni altera la detecció del cicle.
28. Tots els textos visibles de la interfície tenen traducció completa en anglès, castellà i català.
29. La icona de marca aprovada és `docs/appliance_cycle_monitor_icon.svg`; qualsevol canvi posterior de disseny necessita aprovació de l'usuari.

## 9. Qualitat i proves

- La suite ha d'incloure proves unitàries i proves de component de Home Assistant, amb fixtures i dades de prova deterministes. Les proves no han de dependre de dispositius reals ni de serveis externs.
- La cobertura combinada de codi de la integració, calculada a partir de les proves unitàries i de component juntes, ha de ser **com a mínim del 95%**. Un únic check de cobertura agregada ha d'executar o combinar ambdues suites i aplicar `--cov-fail-under=95`; no s'exigeix que cada suite individual assoleixi el 95%. Una cobertura combinada inferior ha de fer fallar el check.
- Les proves han de cobrir com a mínim els fluxos de configuració en tres passos, crear/editar/eliminar dispositius, persistència, conversió d'unitats, llindars i histèresi, temps màxim i acció única d'avís, finalització pel switch, límit i persistència de les accions repetides de «pendent de buidar», retard inicial i cancel·lació en obrir la porta, neteja manual de l'estat pendent amb sensor disponible o no disponible, switch opcional, inici/final del cicle, càlcul i reinici de l'energia, càlcul de temps restant, estat de porta, execució i fallada d'accions, i entitats no disponibles.
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
- L'estructura ha de seguir el format d'integració HACS: `custom_components/appliance_cycle_monitor/`, manifest vàlid, configuració HACS de categoria `integration`, fitxers de traducció i metadades necessaris per a Home Assistant.
- Abans de cada publicació, han de passar HACS validation, Hassfest, tests i cobertura. El README ha d'incloure badges d'estat dels workflows i de cobertura.
- Les versions han de seguir Semantic Versioning. La versió del manifest, el tag Git i la release de GitHub han de coincidir; cada release ha d'actualitzar el changelog.
- La submissió al repositori per defecte de HACS és un pas de publicació separat: preparar-la i demanar-ne la inclusió quan el repositori i la primera release compleixin els requisits de HACS.

## 12. Idiomes i marca

- L'anglès és l'idioma font per a les cadenes de la interfície i la documentació principal del projecte.
- Tots els textos visibles a Home Assistant han d'utilitzar claus de traducció; no s'han de codificar directament dins la lògica de la integració.
- La interfície ha de tenir traduccions completes en anglès, castellà (`es`) i català (`ca`), inclosos els tres passos de configuració, els noms i estats de les entitats, les opcions, les validacions i els errors.
- Les traduccions han de mantenir el mateix conjunt de claus i significat. Les proves o validacions han de detectar claus absents o sobrants.
- La proposta `docs/appliance_cycle_monitor_icon.svg` ha estat aprovada per l'usuari com a icona de marca. Cal conservar el disseny aprovat en preparar els recursos finals de marca per a la integració.
- La icona ha de ser llegible a mida petita i sobre fons clars i foscos, representar la gestió de cicles d'electrodomèstics de manera genèrica i no identificar-se només amb un tipus d'aparell.

## 13. Decisions pendents

- Confirmar el nom i la finalitat exacta del grup d'accions general de la captura; aquí s'interpreta com les accions en finalitzar el cicle.
- Definir límits mínims i màxims dels controls numèrics; els valors inicials sí que queden fixats en aquest document.
- Definir les versions mínimes de Home Assistant i Python quan s'iniciï la implementació.

**Data d'actualització**: 2026-10-26