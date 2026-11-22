/**
 * Privacy policy and terms of use — DRAFT, not legal advice. Facts about data flows were checked
 * against the code on 2026-11-22 (what reaches Gemini, cookies, processors). Items in [brackets]
 * must be filled in or confirmed by the owner before publishing; legal review is the owner's.
 */
import type { Language } from './preferences';

export interface LegalSection { title: string; body: string[] }
export interface LegalDoc { title: string; draft: string; updated: string; sections: LegalSection[] }

const UPDATED = '2026-11-22';

const privacy: Record<Language, LegalDoc> = {
  en: {
    title: 'Privacy policy',
    draft: 'DRAFT — not yet reviewed by a lawyer. Items in [brackets] are to be completed by the operator.',
    updated: UPDATED,
    sections: [
      { title: 'Who is responsible', body: ['Data controller: [name / company, address]. Contact for privacy questions: [e-mail address].'] },
      { title: 'What we store', body: [
        'Account: your e-mail address and login data (managed by Supabase Auth; we never see your password).',
        'Reading data: your library, shelves, favourites and ratings; your notes, review cards and review history; your preferences (genres, language, theme).',
        'Technical logs: request time, duration and a random request id. Note contents are not written to logs.',
        'If error reporting is enabled: technical error reports without your identity, notes, e-mail address or search text.'] },
      { title: 'Reminders', body: ["Only if you turn them on in Settings. We store your channel (e-mail or notification), time, time zone, quiet days and language, and for notifications this device's push address and keys. E-mails are sent through Resend; notifications through your browser maker's push service (e.g. Google, Apple, Mozilla) and contain only the number of questions due. We record when a reminder was sent and two usage events (reminder opened, review session completed) to see whether reminders help; no advertising or third-party analytics. Every e-mail has a one-click unsubscribe link."] },
      { title: 'Artificial intelligence (Google Gemini)', body: [
        'When you save a key takeaway, its text (up to 1,500 characters) and the book title are sent to Google Gemini to turn it into a review question.',
        'When you use Ask AI, your question and data about catalogue books are sent to Google Gemini to search the catalogue and write the answer.',
        'Your e-mail address and account id are not sent to Gemini. Whether Google may use this content to improve its services depends on the Gemini plan in use: [operator to confirm the plan and Google\'s terms for it].'] },
      { title: 'Why we process it (legal bases)', body: [
        'To provide the service you signed up for (KVKK art. 5(2)(c), GDPR art. 6(1)(b)); to keep the service secure and working (legitimate interest, GDPR art. 6(1)(f)).'] },
      { title: 'Service providers and transfers abroad', body: [
        'Supabase (database and login), Render (application server), Vercel (website hosting), Google (Gemini AI), and Sentry if error reporting is enabled. Some of them process data outside Turkey and the EU: [operator to list regions and the safeguards used, KVKK art. 9 / GDPR chapter V].'] },
      { title: 'How long we keep it', body: [
        'As long as your account exists. When you delete your account, your data is deleted at once; provider backups expire within [backup retention period].'] },
      { title: 'Your rights', body: [
        'You can access, correct, export and delete your data (KVKK art. 11, GDPR art. 15–22). Download everything and delete your account yourself under Settings → Account. For anything else, write to [e-mail address]. You may also complain to the KVKK Board or your EU data protection authority.'] },
      { title: 'Cookies and local storage', body: [
        'Only what the app needs: the login session and your language, theme and colour choices. Your Ask AI history and reading goal are kept only in your browser. No advertising or analytics cookies.'] },
      { title: 'Changes', body: ['We will announce material changes in the app before they take effect.'] },
    ],
  },
  tr: {
    title: 'Gizlilik politikası',
    draft: 'TASLAK — henüz bir hukukçu tarafından incelenmedi. [Köşeli parantez] içindeki bölümler işletmeci tarafından doldurulacaktır.',
    updated: UPDATED,
    sections: [
      { title: 'Veri sorumlusu', body: ['Veri sorumlusu: [ad / şirket, adres]. Gizlilik soruları için iletişim: [e-posta adresi].'] },
      { title: 'Hangi verileri saklıyoruz', body: [
        'Hesap: e-posta adresin ve giriş bilgilerin (Supabase Auth tarafından yönetilir; şifreni biz hiçbir zaman görmeyiz).',
        'Okuma verileri: kütüphanen, rafların, favorilerin ve puanların; notların, tekrar kartların ve tekrar geçmişin; tercihlerin (türler, dil, tema).',
        'Teknik kayıtlar: istek zamanı, süresi ve rastgele bir istek numarası. Not içerikleri kayıtlara yazılmaz.',
        'Hata raporlama açıksa: kimliğin, notların, e-posta adresin ve arama metnin olmadan teknik hata raporları.'] },
      { title: 'Hatırlatmalar', body: ["Yalnızca Ayarlar'dan açarsan. Kanalını (e-posta veya bildirim), saatini, saat dilimini, sessiz günlerini ve dilini; bildirimler için bu cihazın push adresini ve anahtarlarını saklarız. E-postalar Resend üzerinden, bildirimler tarayıcının push servisi (ör. Google, Apple, Mozilla) üzerinden gönderilir ve yalnızca bekleyen soru sayısını içerir. Hatırlatmaların işe yarayıp yaramadığını görmek için gönderim zamanını ve iki kullanım olayını (hatırlatma açıldı, tekrar oturumu tamamlandı) kaydederiz; reklam veya üçüncü taraf analitik yoktur. Her e-postada tek tıkla abonelikten çıkma bağlantısı bulunur."] },
      { title: 'Yapay zekâ (Google Gemini)', body: [
        'Önemli bir çıkarım kaydettiğinde, metni (en fazla 1.500 karakter) ve kitabın adı, bir tekrar sorusuna dönüştürülmesi için Google Gemini\'ye gönderilir.',
        'Yapay zekâya sor özelliğini kullandığında, sorun ve katalogdaki kitaplara ait bilgiler, katalogda arama yapmak ve cevabı yazmak için Google Gemini\'ye gönderilir.',
        'E-posta adresin ve hesap numaran Gemini\'ye gönderilmez. Google\'ın bu içeriği hizmetlerini geliştirmek için kullanıp kullanamayacağı, kullanılan Gemini planına bağlıdır: [işletmeci planı ve Google\'ın o plana ait koşullarını teyit edecek].'] },
      { title: 'Neden işliyoruz (hukuki sebepler)', body: [
        'Kaydolduğun hizmeti sunmak için (KVKK md. 5/2-c, GDPR md. 6/1-b); hizmeti güvenli ve çalışır tutmak için (meşru menfaat, GDPR md. 6/1-f).'] },
      { title: 'Hizmet sağlayıcılar ve yurt dışına aktarım', body: [
        'Supabase (veritabanı ve giriş), Render (uygulama sunucusu), Vercel (web sitesi barındırma), Google (Gemini yapay zekâ) ve hata raporlama açıksa Sentry. Bunların bir kısmı verileri Türkiye ve AB dışında işler: [işletmeci bölgeleri ve kullanılan güvenceleri listeleyecek, KVKK md. 9 / GDPR V. bölüm].'] },
      { title: 'Ne kadar saklıyoruz', body: [
        'Hesabın var olduğu sürece. Hesabını sildiğinde verilerin hemen silinir; sağlayıcıların yedekleri [yedek saklama süresi] içinde kendiliğinden silinir.'] },
      { title: 'Hakların', body: [
        'Verilerine erişebilir, onları düzeltebilir, indirebilir ve silebilirsin (KVKK md. 11, GDPR md. 15–22). Ayarlar → Hesap bölümünden her şeyi indirebilir ve hesabını kendin silebilirsin. Diğer talepler için [e-posta adresi] adresine yaz. Kişisel Verileri Koruma Kurulu\'na veya AB\'deki veri koruma otoritene şikâyette de bulunabilirsin.'] },
      { title: 'Çerezler ve yerel depolama', body: [
        'Yalnızca uygulamanın ihtiyaç duyduğu kadarı: oturum ve dil, tema, renk seçimlerin. Yapay zekâ sohbet geçmişin ve okuma hedefin yalnızca tarayıcında tutulur. Reklam veya analiz çerezi yoktur.'] },
      { title: 'Değişiklikler', body: ['Önemli değişiklikleri yürürlüğe girmeden önce uygulamada duyururuz.'] },
    ],
  },
  de: {
    title: 'Datenschutzerklärung',
    draft: 'ENTWURF — noch nicht juristisch geprüft. Angaben in [Klammern] ergänzt der Betreiber.',
    updated: UPDATED,
    sections: [
      { title: 'Verantwortlicher', body: ['Verantwortlicher: [Name / Firma, Anschrift]. Kontakt für Datenschutzfragen: [E-Mail-Adresse].'] },
      { title: 'Welche Daten wir speichern', body: [
        'Konto: deine E-Mail-Adresse und Anmeldedaten (verwaltet von Supabase Auth; dein Passwort sehen wir nie).',
        'Lesedaten: Bibliothek, Regale, Favoriten und Bewertungen; Notizen, Lernkarten und Lernverlauf; Einstellungen (Genres, Sprache, Design).',
        'Technische Protokolle: Zeitpunkt, Dauer und eine zufällige Anfrage-ID. Notizinhalte werden nicht protokolliert.',
        'Falls die Fehlerberichterstattung aktiv ist: technische Fehlerberichte ohne deine Identität, Notizen, E-Mail-Adresse oder Suchtexte.'] },
      { title: 'Erinnerungen', body: ["Nur wenn du sie in den Einstellungen einschaltest. Wir speichern Kanal (E-Mail oder Mitteilung), Uhrzeit, Zeitzone, Ruhetage und Sprache, für Mitteilungen außerdem die Push-Adresse und Schlüssel dieses Geräts. E-Mails werden über Resend versendet, Mitteilungen über den Push-Dienst deines Browserherstellers (z. B. Google, Apple, Mozilla) und enthalten nur die Zahl fälliger Fragen. Wir speichern, wann eine Erinnerung versendet wurde, und zwei Nutzungsereignisse (Erinnerung geöffnet, Wiederholung abgeschlossen), um zu sehen, ob Erinnerungen helfen; keine Werbung, keine Analyse durch Dritte. Jede E-Mail enthält einen Abmeldelink mit einem Klick."] },
      { title: 'Künstliche Intelligenz (Google Gemini)', body: [
        'Wenn du eine wichtige Erkenntnis speicherst, werden ihr Text (bis zu 1.500 Zeichen) und der Buchtitel an Google Gemini gesendet, um daraus eine Lernfrage zu machen.',
        'Wenn du „KI fragen“ nutzt, werden deine Frage und Daten zu Katalogbüchern an Google Gemini gesendet, um den Katalog zu durchsuchen und die Antwort zu schreiben.',
        'Deine E-Mail-Adresse und Konto-ID werden nicht an Gemini gesendet. Ob Google diese Inhalte zur Verbesserung seiner Dienste nutzen darf, hängt vom verwendeten Gemini-Tarif ab: [Betreiber bestätigt Tarif und Googles Bedingungen dafür].'] },
      { title: 'Zwecke und Rechtsgrundlagen', body: [
        'Bereitstellung des Dienstes, für den du dich angemeldet hast (Art. 6 Abs. 1 lit. b DSGVO); Sicherheit und Betrieb des Dienstes (berechtigtes Interesse, Art. 6 Abs. 1 lit. f DSGVO).'] },
      { title: 'Dienstleister und Übermittlung ins Ausland', body: [
        'Supabase (Datenbank und Anmeldung), Render (Anwendungsserver), Vercel (Website-Hosting), Google (Gemini-KI) und Sentry, falls die Fehlerberichterstattung aktiv ist. Einige verarbeiten Daten außerhalb der EU: [Betreiber nennt Regionen und Garantien, Kapitel V DSGVO].'] },
      { title: 'Speicherdauer', body: [
        'Solange dein Konto besteht. Wenn du dein Konto löschst, werden deine Daten sofort gelöscht; Sicherungen der Anbieter laufen innerhalb von [Aufbewahrungsfrist] ab.'] },
      { title: 'Deine Rechte', body: [
        'Du kannst deine Daten einsehen, berichtigen, exportieren und löschen (Art. 15–22 DSGVO). Unter Einstellungen → Konto lädst du alles herunter und löschst dein Konto selbst. Für alles Weitere schreib an [E-Mail-Adresse]. Du kannst dich auch bei einer Datenschutzaufsichtsbehörde beschweren.'] },
      { title: 'Cookies und lokaler Speicher', body: [
        'Nur, was die App braucht: die Anmeldesitzung sowie deine Sprach-, Design- und Farbwahl. Dein KI-Chatverlauf und dein Leseziel bleiben nur in deinem Browser. Keine Werbe- oder Analyse-Cookies.'] },
      { title: 'Änderungen', body: ['Wesentliche Änderungen kündigen wir in der App an, bevor sie gelten.'] },
    ],
  },
  es: {
    title: 'Política de privacidad',
    draft: 'BORRADOR — aún no revisado por un abogado. Los puntos entre [corchetes] los completa el operador.',
    updated: UPDATED,
    sections: [
      { title: 'Responsable', body: ['Responsable del tratamiento: [nombre / empresa, dirección]. Contacto de privacidad: [correo electrónico].'] },
      { title: 'Qué datos guardamos', body: [
        'Cuenta: tu correo y datos de acceso (gestionados por Supabase Auth; nunca vemos tu contraseña).',
        'Datos de lectura: biblioteca, estanterías, favoritos y valoraciones; notas, tarjetas de repaso e historial; preferencias (géneros, idioma, tema).',
        'Registros técnicos: hora, duración y un identificador aleatorio de la solicitud. El contenido de las notas no se registra.',
        'Si el informe de errores está activo: informes técnicos sin tu identidad, notas, correo ni textos de búsqueda.'] },
      { title: 'Recordatorios', body: ["Solo si los activas en Ajustes. Guardamos el canal (correo o notificación), la hora, la zona horaria, los días sin recordatorio y el idioma, y para las notificaciones la dirección push y las claves de este dispositivo. Los correos se envían a través de Resend; las notificaciones, a través del servicio push del fabricante de tu navegador (p. ej. Google, Apple, Mozilla) y solo contienen el número de preguntas pendientes. Registramos cuándo se envió un recordatorio y dos eventos de uso (recordatorio abierto, sesión de repaso completada) para saber si los recordatorios ayudan; sin publicidad ni analítica de terceros. Cada correo incluye un enlace para darse de baja con un clic."] },
      { title: 'Inteligencia artificial (Google Gemini)', body: [
        'Cuando guardas una idea clave, su texto (hasta 1.500 caracteres) y el título del libro se envían a Google Gemini para convertirla en una pregunta de repaso.',
        'Cuando usas Preguntar a la IA, tu pregunta y datos de libros del catálogo se envían a Google Gemini para buscar en el catálogo y redactar la respuesta.',
        'Tu correo y tu identificador de cuenta no se envían a Gemini. Que Google pueda usar este contenido para mejorar sus servicios depende del plan de Gemini utilizado: [el operador confirma el plan y sus condiciones].'] },
      { title: 'Finalidades y bases jurídicas', body: [
        'Prestar el servicio que contrataste (art. 6.1.b RGPD); mantener el servicio seguro y operativo (interés legítimo, art. 6.1.f RGPD).'] },
      { title: 'Proveedores y transferencias internacionales', body: [
        'Supabase (base de datos y acceso), Render (servidor de la aplicación), Vercel (alojamiento web), Google (IA Gemini) y Sentry si el informe de errores está activo. Algunos tratan datos fuera de la UE: [el operador indica regiones y garantías, capítulo V RGPD].'] },
      { title: 'Plazo de conservación', body: [
        'Mientras exista tu cuenta. Al eliminarla, tus datos se borran de inmediato; las copias de seguridad de los proveedores caducan en [plazo de conservación].'] },
      { title: 'Tus derechos', body: [
        'Puedes acceder, rectificar, exportar y suprimir tus datos (arts. 15–22 RGPD). En Ajustes → Cuenta puedes descargar todo y eliminar tu cuenta tú mismo. Para lo demás, escribe a [correo electrónico]. También puedes reclamar ante una autoridad de protección de datos.'] },
      { title: 'Cookies y almacenamiento local', body: [
        'Solo lo necesario: la sesión y tus elecciones de idioma, tema y color. Tu historial del chat con la IA y tu objetivo de lectura se guardan solo en tu navegador. Sin cookies publicitarias ni analíticas.'] },
      { title: 'Cambios', body: ['Anunciaremos en la aplicación los cambios importantes antes de que entren en vigor.'] },
    ],
  },
  fr: {
    title: 'Politique de confidentialité',
    draft: 'PROJET — pas encore relu par un juriste. Les éléments entre [crochets] sont à compléter par l\'exploitant.',
    updated: UPDATED,
    sections: [
      { title: 'Responsable du traitement', body: ['Responsable : [nom / société, adresse]. Contact confidentialité : [adresse e-mail].'] },
      { title: 'Données conservées', body: [
        'Compte : votre adresse e-mail et vos données de connexion (gérées par Supabase Auth ; nous ne voyons jamais votre mot de passe).',
        'Données de lecture : bibliothèque, étagères, favoris et notes attribuées ; vos notes, cartes de révision et historique ; vos préférences (genres, langue, thème).',
        'Journaux techniques : heure, durée et un identifiant de requête aléatoire. Le contenu des notes n\'est pas journalisé.',
        'Si le signalement d\'erreurs est activé : rapports techniques sans votre identité, vos notes, votre e-mail ni vos recherches.'] },
      { title: 'Rappels', body: ["Uniquement si vous les activez dans les paramètres. Nous enregistrons le canal (e-mail ou notification), l'heure, le fuseau horaire, les jours sans rappel et la langue, et pour les notifications l'adresse push et les clés de cet appareil. Les e-mails sont envoyés via Resend ; les notifications via le service push de l'éditeur de votre navigateur (p. ex. Google, Apple, Mozilla) et ne contiennent que le nombre de questions dues. Nous enregistrons l'heure d'envoi d'un rappel et deux événements d'usage (rappel ouvert, séance de révision terminée) pour savoir si les rappels aident ; ni publicité ni analyse tierce. Chaque e-mail contient un lien de désabonnement en un clic."] },
      { title: 'Intelligence artificielle (Google Gemini)', body: [
        'Lorsque vous enregistrez une idée clé, son texte (jusqu\'à 1 500 caractères) et le titre du livre sont envoyés à Google Gemini pour en faire une question de révision.',
        'Lorsque vous utilisez « Demander à l\'IA », votre question et des données sur les livres du catalogue sont envoyées à Google Gemini pour chercher dans le catalogue et rédiger la réponse.',
        'Votre e-mail et votre identifiant de compte ne sont pas envoyés à Gemini. La possibilité pour Google d\'utiliser ces contenus pour améliorer ses services dépend de l\'offre Gemini utilisée : [l\'exploitant confirme l\'offre et ses conditions].'] },
      { title: 'Finalités et bases légales', body: [
        'Fournir le service auquel vous vous êtes inscrit (art. 6.1.b RGPD) ; assurer la sécurité et le fonctionnement du service (intérêt légitime, art. 6.1.f RGPD).'] },
      { title: 'Prestataires et transferts hors UE', body: [
        'Supabase (base de données et connexion), Render (serveur applicatif), Vercel (hébergement du site), Google (IA Gemini) et Sentry si le signalement d\'erreurs est activé. Certains traitent des données hors de l\'UE : [l\'exploitant précise régions et garanties, chapitre V RGPD].'] },
      { title: 'Durée de conservation', body: [
        'Tant que votre compte existe. Lorsque vous supprimez votre compte, vos données sont effacées immédiatement ; les sauvegardes des prestataires expirent sous [durée de conservation].'] },
      { title: 'Vos droits', body: [
        'Vous pouvez accéder à vos données, les rectifier, les exporter et les effacer (art. 15 à 22 RGPD). Dans Paramètres → Compte, vous téléchargez tout et supprimez votre compte vous-même. Pour le reste, écrivez à [adresse e-mail]. Vous pouvez aussi saisir une autorité de protection des données.'] },
      { title: 'Cookies et stockage local', body: [
        'Uniquement le nécessaire : la session et vos choix de langue, de thème et de couleurs. L\'historique de vos échanges avec l\'IA et votre objectif de lecture restent dans votre navigateur. Aucun cookie publicitaire ni de mesure d\'audience.'] },
      { title: 'Modifications', body: ['Nous annoncerons dans l\'application les changements importants avant leur entrée en vigueur.'] },
    ],
  },
  it: {
    title: 'Informativa sulla privacy',
    draft: 'BOZZA — non ancora esaminata da un legale. Le voci tra [parentesi] vanno completate dal gestore.',
    updated: UPDATED,
    sections: [
      { title: 'Titolare del trattamento', body: ['Titolare: [nome / società, indirizzo]. Contatto privacy: [indirizzo e-mail].'] },
      { title: 'Quali dati conserviamo', body: [
        'Account: il tuo indirizzo e-mail e i dati di accesso (gestiti da Supabase Auth; non vediamo mai la tua password).',
        'Dati di lettura: libreria, scaffali, preferiti e valutazioni; note, schede di ripasso e cronologia; preferenze (generi, lingua, tema).',
        'Log tecnici: orario, durata e un identificativo casuale della richiesta. Il contenuto delle note non viene registrato.',
        'Se la segnalazione degli errori è attiva: report tecnici senza la tua identità, note, e-mail o testi di ricerca.'] },
      { title: 'Promemoria', body: ["Solo se li attivi nelle Impostazioni. Salviamo il canale (e-mail o notifica), l'ora, il fuso orario, i giorni senza promemoria e la lingua, e per le notifiche l'indirizzo push e le chiavi di questo dispositivo. Le e-mail vengono inviate tramite Resend; le notifiche tramite il servizio push del produttore del tuo browser (es. Google, Apple, Mozilla) e contengono solo il numero di domande da ripassare. Registriamo quando è stato inviato un promemoria e due eventi d'uso (promemoria aperto, sessione di ripasso completata) per capire se i promemoria aiutano; niente pubblicità né analisi di terze parti. Ogni e-mail contiene un link per annullare l'iscrizione con un clic."] },
      { title: 'Intelligenza artificiale (Google Gemini)', body: [
        'Quando salvi un concetto chiave, il suo testo (fino a 1.500 caratteri) e il titolo del libro vengono inviati a Google Gemini per trasformarlo in una domanda di ripasso.',
        'Quando usi «Chiedi all\'IA», la tua domanda e dati sui libri del catalogo vengono inviati a Google Gemini per cercare nel catalogo e scrivere la risposta.',
        'La tua e-mail e il tuo identificativo di account non vengono inviati a Gemini. Se Google possa usare questi contenuti per migliorare i propri servizi dipende dal piano Gemini utilizzato: [il gestore conferma il piano e le relative condizioni].'] },
      { title: 'Finalità e basi giuridiche', body: [
        'Fornire il servizio a cui ti sei registrato (art. 6.1.b GDPR); mantenere il servizio sicuro e funzionante (legittimo interesse, art. 6.1.f GDPR).'] },
      { title: 'Fornitori e trasferimenti extra UE', body: [
        'Supabase (database e accesso), Render (server applicativo), Vercel (hosting del sito), Google (IA Gemini) e Sentry se la segnalazione degli errori è attiva. Alcuni trattano dati fuori dall\'UE: [il gestore indica regioni e garanzie, capo V GDPR].'] },
      { title: 'Conservazione', body: [
        'Finché esiste il tuo account. Quando lo elimini, i tuoi dati vengono cancellati subito; i backup dei fornitori scadono entro [periodo di conservazione].'] },
      { title: 'I tuoi diritti', body: [
        'Puoi accedere ai tuoi dati, rettificarli, esportarli e cancellarli (artt. 15–22 GDPR). In Impostazioni → Account puoi scaricare tutto ed eliminare l\'account da solo. Per il resto scrivi a [indirizzo e-mail]. Puoi anche presentare reclamo a un\'autorità di protezione dei dati.'] },
      { title: 'Cookie e archiviazione locale', body: [
        'Solo ciò che serve all\'app: la sessione e le tue scelte di lingua, tema e colori. La cronologia della chat con l\'IA e l\'obiettivo di lettura restano solo nel tuo browser. Nessun cookie pubblicitario o di analisi.'] },
      { title: 'Modifiche', body: ['Annunceremo nell\'app le modifiche importanti prima che entrino in vigore.'] },
    ],
  },
};

const terms: Record<Language, LegalDoc> = {
  en: {
    title: 'Terms of use', draft: privacy.en.draft, updated: UPDATED,
    sections: [
      { title: 'The service', body: ['Libris helps you find books, keep reading notes and review what you learned. It is provided by [operator].'] },
      { title: 'Your account', body: ['Keep your login details safe. You are responsible for activity under your account. You can delete your account at any time in Settings.'] },
      { title: 'Your content', body: ['Your notes stay yours. You allow us to store and process them only to provide the service, including sending them to Google Gemini as described in the privacy policy.'] },
      { title: 'AI-generated content', body: ['Questions and answers written by AI can be wrong or incomplete. Check important information yourself.'] },
      { title: 'Shared catalogue', body: ['Books you add to the catalogue become visible to all readers. Add only accurate book information and nothing unlawful.'] },
      { title: 'Acceptable use', body: ['Do not misuse the service: no attacks, automated scraping, or attempts to access other people\'s data.'] },
      { title: 'Availability', body: ['We do our best to keep Libris running but cannot guarantee uninterrupted service. After a quiet period the server may need up to a minute to start.'] },
      { title: 'Liability and law', body: ['[Limitation of liability and governing law to be completed by the operator after legal review.]'] },
      { title: 'Contact', body: ['[e-mail address]'] },
    ],
  },
  tr: {
    title: 'Kullanım şartları', draft: privacy.tr.draft, updated: UPDATED,
    sections: [
      { title: 'Hizmet', body: ['Libris kitap bulmana, okuma notları tutmana ve öğrendiklerini tekrar etmene yardımcı olur. Hizmeti [işletmeci] sunar.'] },
      { title: 'Hesabın', body: ['Giriş bilgilerini güvende tut. Hesabınla yapılan işlemlerden sen sorumlusun. Hesabını istediğin zaman Ayarlar\'dan silebilirsin.'] },
      { title: 'İçeriğin', body: ['Notların senindir. Bunları yalnızca hizmeti sunmak için saklamamıza ve işlememize izin verirsin; buna gizlilik politikasında anlatıldığı şekilde Google Gemini\'ye gönderilmeleri de dahildir.'] },
      { title: 'Yapay zekâ içerikleri', body: ['Yapay zekânın yazdığı sorular ve cevaplar yanlış ya da eksik olabilir. Önemli bilgileri kendin kontrol et.'] },
      { title: 'Ortak katalog', body: ['Kataloğa eklediğin kitaplar tüm okurlara görünür. Yalnızca doğru kitap bilgileri ekle; hukuka aykırı içerik ekleme.'] },
      { title: 'Kabul edilebilir kullanım', body: ['Hizmeti kötüye kullanma: saldırı, otomatik veri toplama ya da başkalarının verilerine erişme girişimi yasaktır.'] },
      { title: 'Erişilebilirlik', body: ['Libris\'i çalışır tutmak için elimizden geleni yaparız ama kesintisiz hizmet garanti edemeyiz. Uzun bir aradan sonra sunucunun açılması bir dakikayı bulabilir.'] },
      { title: 'Sorumluluk ve uygulanacak hukuk', body: ['[Sorumluluğun sınırlandırılması ve uygulanacak hukuk, hukuki incelemeden sonra işletmeci tarafından doldurulacaktır.]'] },
      { title: 'İletişim', body: ['[e-posta adresi]'] },
    ],
  },
  de: {
    title: 'Nutzungsbedingungen', draft: privacy.de.draft, updated: UPDATED,
    sections: [
      { title: 'Der Dienst', body: ['Libris hilft dir, Bücher zu finden, Lesenotizen zu führen und Gelerntes zu wiederholen. Anbieter ist [Betreiber].'] },
      { title: 'Dein Konto', body: ['Halte deine Zugangsdaten geheim. Du bist für Aktivitäten unter deinem Konto verantwortlich. Du kannst dein Konto jederzeit in den Einstellungen löschen.'] },
      { title: 'Deine Inhalte', body: ['Deine Notizen gehören dir. Du erlaubst uns, sie nur zur Erbringung des Dienstes zu speichern und zu verarbeiten, einschließlich der Übermittlung an Google Gemini wie in der Datenschutzerklärung beschrieben.'] },
      { title: 'KI-generierte Inhalte', body: ['Von der KI geschriebene Fragen und Antworten können falsch oder unvollständig sein. Prüfe wichtige Informationen selbst.'] },
      { title: 'Gemeinsamer Katalog', body: ['Bücher, die du dem Katalog hinzufügst, sehen alle Leser. Füge nur korrekte Buchangaben und nichts Rechtswidriges hinzu.'] },
      { title: 'Zulässige Nutzung', body: ['Missbrauche den Dienst nicht: keine Angriffe, kein automatisiertes Auslesen, keine Versuche, auf Daten anderer zuzugreifen.'] },
      { title: 'Verfügbarkeit', body: ['Wir bemühen uns, Libris verfügbar zu halten, können aber keinen unterbrechungsfreien Betrieb garantieren. Nach einer Ruhepause kann der Serverstart bis zu einer Minute dauern.'] },
      { title: 'Haftung und Recht', body: ['[Haftungsbeschränkung und anwendbares Recht ergänzt der Betreiber nach juristischer Prüfung.]'] },
      { title: 'Kontakt', body: ['[E-Mail-Adresse]'] },
    ],
  },
  es: {
    title: 'Condiciones de uso', draft: privacy.es.draft, updated: UPDATED,
    sections: [
      { title: 'El servicio', body: ['Libris te ayuda a encontrar libros, tomar notas de lectura y repasar lo aprendido. Lo presta [operador].'] },
      { title: 'Tu cuenta', body: ['Protege tus datos de acceso. Eres responsable de la actividad de tu cuenta. Puedes eliminarla en cualquier momento desde Ajustes.'] },
      { title: 'Tu contenido', body: ['Tus notas son tuyas. Nos permites guardarlas y tratarlas solo para prestar el servicio, incluido su envío a Google Gemini según la política de privacidad.'] },
      { title: 'Contenido generado por IA', body: ['Las preguntas y respuestas escritas por la IA pueden ser incorrectas o incompletas. Comprueba tú mismo la información importante.'] },
      { title: 'Catálogo común', body: ['Los libros que añades al catálogo los ven todos los lectores. Añade solo información correcta y nada ilícito.'] },
      { title: 'Uso aceptable', body: ['No hagas un uso indebido: nada de ataques, extracción automatizada ni intentos de acceder a datos ajenos.'] },
      { title: 'Disponibilidad', body: ['Hacemos lo posible por mantener Libris en marcha, pero no garantizamos un servicio ininterrumpido. Tras un periodo de inactividad el servidor puede tardar hasta un minuto en arrancar.'] },
      { title: 'Responsabilidad y ley aplicable', body: ['[El operador completará la limitación de responsabilidad y la ley aplicable tras la revisión legal.]'] },
      { title: 'Contacto', body: ['[correo electrónico]'] },
    ],
  },
  fr: {
    title: 'Conditions d\'utilisation', draft: privacy.fr.draft, updated: UPDATED,
    sections: [
      { title: 'Le service', body: ['Libris vous aide à trouver des livres, à prendre des notes de lecture et à réviser ce que vous avez appris. Il est fourni par [exploitant].'] },
      { title: 'Votre compte', body: ['Protégez vos identifiants. Vous êtes responsable de l\'activité de votre compte. Vous pouvez le supprimer à tout moment dans les paramètres.'] },
      { title: 'Vos contenus', body: ['Vos notes vous appartiennent. Vous nous autorisez à les conserver et à les traiter uniquement pour fournir le service, y compris leur envoi à Google Gemini comme décrit dans la politique de confidentialité.'] },
      { title: 'Contenus générés par l\'IA', body: ['Les questions et réponses rédigées par l\'IA peuvent être fausses ou incomplètes. Vérifiez vous-même les informations importantes.'] },
      { title: 'Catalogue commun', body: ['Les livres que vous ajoutez au catalogue sont visibles par tous. N\'ajoutez que des informations exactes et rien d\'illicite.'] },
      { title: 'Usage acceptable', body: ['N\'abusez pas du service : pas d\'attaques, d\'extraction automatisée ni de tentative d\'accès aux données d\'autrui.'] },
      { title: 'Disponibilité', body: ['Nous faisons de notre mieux pour que Libris fonctionne, sans pouvoir garantir un service ininterrompu. Après une période d\'inactivité, le démarrage du serveur peut prendre jusqu\'à une minute.'] },
      { title: 'Responsabilité et droit applicable', body: ['[Limitation de responsabilité et droit applicable à compléter par l\'exploitant après revue juridique.]'] },
      { title: 'Contact', body: ['[adresse e-mail]'] },
    ],
  },
  it: {
    title: 'Termini di utilizzo', draft: privacy.it.draft, updated: UPDATED,
    sections: [
      { title: 'Il servizio', body: ['Libris ti aiuta a trovare libri, prendere appunti di lettura e ripassare ciò che hai imparato. È fornito da [gestore].'] },
      { title: 'Il tuo account', body: ['Proteggi i tuoi dati di accesso. Sei responsabile delle attività del tuo account. Puoi eliminarlo in qualsiasi momento dalle Impostazioni.'] },
      { title: 'I tuoi contenuti', body: ['Le tue note restano tue. Ci autorizzi a conservarle e trattarle solo per fornire il servizio, incluso l\'invio a Google Gemini come descritto nell\'informativa sulla privacy.'] },
      { title: 'Contenuti generati dall\'IA', body: ['Domande e risposte scritte dall\'IA possono essere errate o incomplete. Verifica tu stesso le informazioni importanti.'] },
      { title: 'Catalogo comune', body: ['I libri che aggiungi al catalogo sono visibili a tutti i lettori. Aggiungi solo informazioni corrette e nulla di illecito.'] },
      { title: 'Uso consentito', body: ['Non abusare del servizio: niente attacchi, estrazione automatizzata o tentativi di accedere ai dati altrui.'] },
      { title: 'Disponibilità', body: ['Facciamo il possibile per mantenere Libris attivo, ma non possiamo garantire un servizio ininterrotto. Dopo un periodo di inattività l\'avvio del server può richiedere fino a un minuto.'] },
      { title: 'Responsabilità e legge applicabile', body: ['[Limitazione di responsabilità e legge applicabile da completare a cura del gestore dopo la revisione legale.]'] },
      { title: 'Contatti', body: ['[indirizzo e-mail]'] },
    ],
  },
};

export const LEGAL = { privacy, terms } as const;
export type LegalKind = keyof typeof LEGAL;
