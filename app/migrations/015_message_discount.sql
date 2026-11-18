-- Put the discount into the message a customer actually reads.
--
-- The printed estimate has carried the discount from the beginning. The
-- message sent by WhatsApp did not, so a customer promised ten percent was
-- quoted a total with no sign of where it came from -- and the message is
-- what most of them ever see. The printed copy answers the question only if
-- somebody asks it.
--
-- Two new placeholders: {discount}, the money taken off, and {discount_rate},
-- the percentage when one was agreed rather than a flat amount. Both come
-- back empty when there is no discount, and a line whose placeholders are all
-- empty is dropped whole by the renderer -- label and all -- so the line can
-- sit in the template permanently and appear only when it means something.
--
-- As in migration 005: the template is rewritten only where it is still
-- word-for-word the one that shipped. Anybody who has written their own is
-- left alone, because a migration that silently rewrites somebody's own words
-- to a customer is worse than one that leaves a placeholder unused. Settings
-- lists the placeholders, so a customised template can pick them up by hand.
-- ---------------------------------------------------------------------------

UPDATE settings SET
    message_template_en =
        'Hello {customer},' || char(10) || char(10) ||
        'Here is our estimate {number} from {business}:' || char(10) ||
        '{items}' || char(10) ||
        'Subtotal: {subtotal}' || char(10) ||
        'Discount {discount_rate}: -{discount}' || char(10) ||
        'VAT: {vat}' || char(10) ||
        'Total: {total}' || char(10) ||
        'Valid until {valid_until}.' || char(10) || char(10) ||
        'Reply to this message to go ahead, or call us with any questions.'
WHERE id = 1
  AND message_template_en =
        'Hello {customer},' || char(10) || char(10) ||
        'Here is our estimate {number} from {business}:' || char(10) ||
        '{items}' || char(10) ||
        'Subtotal: {subtotal}' || char(10) ||
        'VAT: {vat}' || char(10) ||
        'Total: {total}' || char(10) ||
        'Valid until {valid_until}.' || char(10) || char(10) ||
        'Reply to this message to go ahead, or call us with any questions.';

UPDATE settings SET
    message_template_ar =
        'مرحباً {customer}،' || char(10) || char(10) ||
        'هذا عرض السعر رقم {number} من {business}:' || char(10) ||
        '{items}' || char(10) ||
        'المجموع قبل الضريبة: {subtotal}' || char(10) ||
        'الخصم {discount_rate}: -{discount}' || char(10) ||
        'ضريبة القيمة المضافة: {vat}' || char(10) ||
        'الإجمالي: {total}' || char(10) ||
        'صالح حتى {valid_until}.' || char(10) || char(10) ||
        'للموافقة يرجى الرد على هذه الرسالة، أو الاتصال بنا لأي استفسار.'
WHERE id = 1
  AND message_template_ar =
        'مرحباً {customer}،' || char(10) || char(10) ||
        'هذا عرض السعر رقم {number} من {business}:' || char(10) ||
        '{items}' || char(10) ||
        'المجموع قبل الضريبة: {subtotal}' || char(10) ||
        'ضريبة القيمة المضافة: {vat}' || char(10) ||
        'الإجمالي: {total}' || char(10) ||
        'صالح حتى {valid_until}.' || char(10) || char(10) ||
        'للموافقة يرجى الرد على هذه الرسالة، أو الاتصال بنا لأي استفسار.';
