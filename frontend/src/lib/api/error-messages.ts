// Тексты ошибок API на языках интерфейса. Язык - uiLocale() из i18n/runtime.

import { uiLocale, type UiLocale } from "@/i18n/runtime";

export { uiLocale };

/** Понятные имена полей API - для перевода ошибок валидации Pydantic. */
export const FIELD_LABELS: Record<UiLocale, Record<string, string>> = {
  ru: {
    from_city: "город отправления",
    to_city: "город доставки",
    from_country: "страна отправления",
    to_country: "страна доставки",
    shipment_type: "тип отправления",
    weight_kg: "вес",
    quantity: "количество",
    width_cm: "ширина",
    height_cm: "высота",
    depth_cm: "глубина",
    email: "email",
    password: "пароль",
    full_name: "имя",
    phone: "телефон",
    iin: "ИИН",
    bin: "БИН",
    company_name: "название компании",
    contact_name: "контактное лицо",
    comment: "комментарий",
    cities: "города",
    tracking_number: "трек-номер",
    address: "адрес",
    city: "город",
    postal_code: "индекс",
    recipient_name: "получатель",
    sender_name: "отправитель",
    rate_quote_id: "тариф",
  },
  kk: {
    from_city: "жөнелту қаласы",
    to_city: "жеткізу қаласы",
    from_country: "жөнелту елі",
    to_country: "жеткізу елі",
    shipment_type: "жөнелтілім түрі",
    weight_kg: "салмақ",
    quantity: "саны",
    width_cm: "ені",
    height_cm: "биіктігі",
    depth_cm: "ұзындығы",
    email: "email",
    password: "құпиясөз",
    full_name: "аты-жөні",
    phone: "телефон",
    iin: "ЖСН",
    bin: "БСН",
    company_name: "компания атауы",
    contact_name: "байланыс тұлғасы",
    comment: "түсініктеме",
    cities: "қалалар",
    tracking_number: "трек-нөмір",
    address: "мекенжай",
    city: "қала",
    postal_code: "индекс",
    recipient_name: "алушы",
    sender_name: "жөнелтуші",
    rate_quote_id: "тариф",
  },
};

/** Шаблоны ошибок валидации. {field}/{Field} - имя поля, {n} - число. */
export const VALIDATION: Record<UiLocale, Record<string, string>> = {
  ru: {
    field: "поле",
    required: "Заполните поле: {field}.",
    minLength: "{Field} — минимум {n} симв.",
    maxLength: "{Field} — максимум {n} симв.",
    email: "Некорректный email.",
    positive: "{Field}: значение больше 0.",
    gte: "{Field}: не меньше {n}.",
    lte: "{Field}: не больше {n}.",
    number: "{Field}: нужно число.",
    invalid: "{Field}: неверное значение.",
  },
  kk: {
    field: "өріс",
    required: "Өрісті толтырыңыз: {field}.",
    minLength: "{Field}: кемінде {n} таңба.",
    maxLength: "{Field}: ең көбі {n} таңба.",
    email: "Email қате.",
    positive: "{Field}: мәні 0-ден үлкен болуы керек.",
    gte: "{Field}: {n}-ден кем емес.",
    lte: "{Field}: {n}-ден аспауы керек.",
    number: "{Field}: сан қажет.",
    invalid: "{Field}: мәні қате.",
  },
};

type MsgId =
  | "emailTaken" | "badCredentials" | "inactive" | "loginRequired" | "sessionExpired"
  | "sessionInvalid" | "accountNotFound" | "userNotFound" | "profileMissing" | "noRights"
  | "carrierProfileMissing" | "orderNotFound" | "orderForbidden" | "deleteUnpaidOnly"
  | "quoteNotFound" | "quoteExpired" | "quoteUnavailable" | "selectRateFirst" | "rateNotFound"
  | "paymentNotFound" | "storageUnavailable" | "uploadFailed" | "serverDown" | "notFound"
  | "actionUnavailable" | "badRequest" | "paymentStatus" | "fileTooBig" | "fileTypeJpgPngPdf"
  | "tooManyAttempts" | "offline" | "conflict" | "fileType" | "checkInput" | "serviceDown"
  | "generic";

export const MESSAGES: Record<UiLocale, Record<MsgId, string>> = {
  ru: {
    emailTaken: "Пользователь с таким email уже зарегистрирован. Войдите или восстановите пароль.",
    badCredentials: "Неверный email или пароль.",
    inactive: "Аккаунт отключён. Обратитесь в поддержку.",
    loginRequired: "Войдите в аккаунт, чтобы продолжить.",
    sessionExpired: "Сессия истекла. Войдите в аккаунт снова.",
    sessionInvalid: "Сессия недействительна. Войдите в аккаунт снова.",
    accountNotFound: "Аккаунт не найден. Войдите в аккаунт снова.",
    userNotFound: "Пользователь не найден.",
    profileMissing: "Профиль не заполнен. Откройте раздел «Профиль» и заполните данные.",
    noRights: "Недостаточно прав для этого действия.",
    carrierProfileMissing: "Профиль перевозчика не найден. Обратитесь в поддержку.",
    orderNotFound: "Заказ не найден.",
    orderForbidden: "Нет доступа к этому заказу.",
    deleteUnpaidOnly: "Удалить можно только неоплаченный заказ.",
    quoteNotFound: "Расчёт не найден. Выполните расчёт заново.",
    quoteExpired: "Расчёт устарел. Выполните расчёт заново.",
    quoteUnavailable: "Расчёт недоступен. Выполните расчёт заново.",
    selectRateFirst: "Сначала выберите тариф.",
    rateNotFound: "Тариф не найден. Выполните расчёт заново.",
    paymentNotFound: "Платёж не найден.",
    storageUnavailable: "Хранилище файлов временно недоступно. Попробуйте позже.",
    uploadFailed: "Не удалось загрузить файл. Попробуйте ещё раз.",
    serverDown: "Сервер временно недоступен. Попробуйте позже.",
    notFound: "Не найдено.",
    actionUnavailable: "Действие недоступно.",
    badRequest: "Некорректный запрос. Проверьте введённые данные.",
    paymentStatus: "Это действие недоступно для текущего статуса оплаты.",
    fileTooBig: "Файл слишком большой. Загрузите файл меньшего размера.",
    fileTypeJpgPngPdf: "Неподдерживаемый тип файла. Загрузите JPG, PNG или PDF.",
    tooManyAttempts: "Слишком много попыток. Подождите немного и попробуйте снова.",
    offline: "Нет соединения с сервером. Проверьте интернет и попробуйте снова.",
    conflict: "Действие конфликтует с текущим состоянием. Обновите страницу и попробуйте снова.",
    fileType: "Неподдерживаемый тип файла.",
    checkInput: "Проверьте введённые данные.",
    serviceDown: "Сервис временно недоступен. Попробуйте через минуту.",
    generic: "Не удалось выполнить действие. Попробуйте ещё раз или напишите в поддержку.",
  },
  kk: {
    emailTaken: "Бұл email-мен пайдаланушы тіркелген. Кіріңіз немесе құпиясөзді қалпына келтіріңіз.",
    badCredentials: "Email немесе құпиясөз қате.",
    inactive: "Аккаунт өшірілген. Қолдау қызметіне хабарласыңыз.",
    loginRequired: "Жалғастыру үшін аккаунтқа кіріңіз.",
    sessionExpired: "Сессия мерзімі аяқталды. Аккаунтқа қайта кіріңіз.",
    sessionInvalid: "Сессия жарамсыз. Аккаунтқа қайта кіріңіз.",
    accountNotFound: "Аккаунт табылмады. Аккаунтқа қайта кіріңіз.",
    userNotFound: "Пайдаланушы табылмады.",
    profileMissing: "Профиль толтырылмаған. «Профиль» бөлімін ашып, деректерді толтырыңыз.",
    noRights: "Бұл әрекетке құқығыңыз жеткіліксіз.",
    carrierProfileMissing: "Тасымалдаушы профилі табылмады. Қолдау қызметіне хабарласыңыз.",
    orderNotFound: "Тапсырыс табылмады.",
    orderForbidden: "Бұл тапсырысқа қолжетімділік жоқ.",
    deleteUnpaidOnly: "Тек төленбеген тапсырысты жоюға болады.",
    quoteNotFound: "Есеп табылмады. Қайта есептеңіз.",
    quoteExpired: "Есептің мерзімі өтті. Қайта есептеңіз.",
    quoteUnavailable: "Есеп қолжетімсіз. Қайта есептеңіз.",
    selectRateFirst: "Алдымен тарифті таңдаңыз.",
    rateNotFound: "Тариф табылмады. Қайта есептеңіз.",
    paymentNotFound: "Төлем табылмады.",
    storageUnavailable: "Файл қоймасы уақытша қолжетімсіз. Кейінірек қайталап көріңіз.",
    uploadFailed: "Файлды жүктеу мүмкін болмады. Қайталап көріңіз.",
    serverDown: "Сервер уақытша қолжетімсіз. Кейінірек қайталап көріңіз.",
    notFound: "Табылмады.",
    actionUnavailable: "Әрекет қолжетімсіз.",
    badRequest: "Сұраныс қате. Енгізілген деректерді тексеріңіз.",
    paymentStatus: "Бұл әрекет төлемнің ағымдағы мәртебесі үшін қолжетімсіз.",
    fileTooBig: "Файл тым үлкен. Кішірек файл жүктеңіз.",
    fileTypeJpgPngPdf: "Файл түрі қолдау көрсетілмейді. JPG, PNG немесе PDF жүктеңіз.",
    tooManyAttempts: "Әрекет тым көп. Біраз күтіп, қайталап көріңіз.",
    offline: "Сервермен байланыс жоқ. Интернетті тексеріп, қайталап көріңіз.",
    conflict: "Әрекет ағымдағы күймен қайшы келеді. Бетті жаңартып, қайталап көріңіз.",
    fileType: "Файл түрі қолдау көрсетілмейді.",
    checkInput: "Енгізілген деректерді тексеріңіз.",
    serviceDown: "Сервис уақытша қолжетімсіз. Бір минуттан соң қайталап көріңіз.",
    generic: "Әрекетті орындау мүмкін болмады. Қайталап көріңіз немесе қолдау қызметіне жазыңыз.",
  },
};

/** Точные (в нижнем регистре) тексты бэкенда → id сообщения. */
export const EXACT: Record<string, MsgId> = {
  "user with this email already exists": "emailTaken",
  "invalid email or password": "badCredentials",
  "user account is inactive": "inactive",
  "current user is inactive": "inactive",
  "authorization credentials are required": "loginRequired",
  "session expired. please log in again.": "sessionExpired",
  "token has expired": "sessionExpired",
  "token subject is missing": "sessionInvalid",
  "invalid token subject": "sessionInvalid",
  "current user not found": "accountNotFound",
  "user not found": "userNotFound",
  "customer profile is missing": "profileMissing",
  "access restricted to administrators": "noRights",
  "access restricted to administrators and operators": "noRights",
  "access restricted to carriers": "noRights",
  "carrier profile not found": "carrierProfileMissing",
  "order draft not found": "orderNotFound",
  "order draft does not belong to the current user": "orderForbidden",
  "only unpaid orders can be deleted": "deleteUnpaidOnly",
  "quote session not found": "quoteNotFound",
  "quote session not found.": "quoteNotFound",
  "quote session has expired": "quoteExpired",
  "invalid or missing quote token": "quoteUnavailable",
  "no selected rate quote for the given quote session": "selectRateFirst",
  "rate quote not found.": "rateNotFound",
  "payment transaction not found": "paymentNotFound",
  "file storage unavailable": "storageUnavailable",
  "file upload failed": "uploadFailed",
  "internal server error": "serverDown",
  "not found": "notFound",
  "forbidden": "noRights",
  "unauthorized": "loginRequired",
  "method not allowed": "actionUnavailable",
  "bad request": "badRequest",
};

/** Шаблоны текстов бэкенда → id сообщения (null - взять текст по HTTP-статусу). */
export const PATTERNS: [RegExp, MsgId | null][] = [
  [/^Cannot (upload proof for|approve|reject) payment in status/i, "paymentStatus"],
  [/^File size exceeds/i, "fileTooBig"],
  [/^Detected file type/i, "fileTypeJpgPngPdf"],
  [/^Allowed:/i, "fileTypeJpgPngPdf"],
  [/^Invalid token/i, "sessionInvalid"],
  [/^Rate limit exceeded/i, "tooManyAttempts"],
  [/^Request failed with status/i, null],
];

export function apiMsg(id: MsgId): string {
  return MESSAGES[uiLocale()][id];
}

/** Сообщение по HTTP-статусу, когда текст бэкенда непригоден для показа. */
export function statusFallback(status: number): string {
  switch (status) {
    case 0: return apiMsg("offline");
    case 400: return apiMsg("badRequest");
    case 401: return apiMsg("loginRequired");
    case 403: return apiMsg("noRights");
    case 404: return apiMsg("notFound");
    case 405: return apiMsg("actionUnavailable");
    case 409: return apiMsg("conflict");
    case 413: return apiMsg("fileTooBig");
    case 415: return apiMsg("fileType");
    case 422: return apiMsg("checkInput");
    case 429: return apiMsg("tooManyAttempts");
    case 500: return apiMsg("serverDown");
    case 502:
    case 503:
    case 504: return apiMsg("serviceDown");
    default: return status >= 500 ? apiMsg("serverDown") : apiMsg("generic");
  }
}
