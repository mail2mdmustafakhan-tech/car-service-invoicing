-- ---------------------------------------------------------------------------
-- 005_message_subtotal_vat.sql  --  show the sum working in the sent message
-- ---------------------------------------------------------------------------
-- The message now lists each item with its price. That exposed a gap: the
-- lines add up to the net figure, the total carries VAT, and a customer
-- reading 450 + 360 followed by "Total: 931.50" has every reason to ask what
-- the extra 121.50 is. A quote that invites that question has failed at the
-- one job it had.
--
-- Two new placeholders, {subtotal} and {vat}, fill the gap.
--
-- The templates are edited in Settings, so this updates them ONLY where the
-- stored text still matches the default this software shipped exactly,
-- character for character. Anyone who has reworded their own message keeps
-- it, untouched -- a migration that silently rewrites somebody's own words
-- is worse than one that leaves a placeholder unused.
-- ---------------------------------------------------------------------------

UPDATE settings SET
    message_template_en =
        'Hello {customer},' || char(10) || char(10) ||
        'Here is our estimate {number} from {business}:' || char(10) ||
        '{items}' || char(10) ||
        'Subtotal: {subtotal}' || char(10) ||
        'VAT: {vat}' || char(10) ||
        'Total: {total}' || char(10) ||
        'Valid until {valid_until}.' || char(10) || char(10) ||
        'Reply to this message to go ahead, or call us with any questions.'
WHERE id = 1
  AND message_template_en =
        'Hello {customer},' || char(10) || char(10) ||
        'Here is our estimate {number} from {business}:' || char(10) ||
        '{items}' || char(10) ||
        'Total: {total}' || char(10) ||
        'Valid until {valid_until}.' || char(10) || char(10) ||
        'Reply to this message to go ahead, or call us with any questions.';

UPDATE settings SET
    message_template_ar =
        'مرحباً {customer}،' || char(10) || char(10) ||
        'هذا عرض السعر رقم {number} من {business}:' || char(10) ||
        '{items}' || char(10) ||
        'المجموع قبل الضريبة: {subtotal}' || char(10) ||
        'ضريبة القيمة المضافة: {vat}' || char(10) ||
        'الإجمالي: {total}' || char(10) ||
        'صالح حتى {valid_until}.' || char(10) || char(10) ||
        'للموافقة يرجى الرد على هذه الرسالة، أو الاتصال بنا لأي استفسار.'
WHERE id = 1
  AND message_template_ar =
        'مرحباً {customer}،' || char(10) || char(10) ||
        'هذا عرض السعر رقم {number} من {business}:' || char(10) ||
        '{items}' || char(10) ||
        'الإجمالي: {total}' || char(10) ||
        'صالح حتى {valid_until}.' || char(10) || char(10) ||
        'للموافقة يرجى الرد على هذه الرسالة، أو الاتصال بنا لأي استفسار.';
