import { X } from 'lucide-react';
import { useState } from 'react';

import type { GaiaQuestion } from '../../domain/run';
import { useI18n } from '../../i18n/I18nProvider';
import { AttachmentLink, GaiaPicker } from './GaiaPicker';

const FIELD = 'min-h-10 w-full rounded-lg border border-line-strong bg-surface px-3 text-sm';

/** The chosen GAIA question, with its attachment and a way to go back to free text. */
function ChosenQuestion({ gaia, onClear }: { gaia: GaiaQuestion; onClear: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex items-start gap-2 rounded-lg border border-line-strong bg-muted p-3 text-sm">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-fg-muted">{t('runs.gaia.selected')}</p>
        <p>{gaia.question}</p>
        {gaia.fileName && <AttachmentLink taskId={gaia.taskId} />}
      </div>
      <button
        type="button"
        onClick={onClear}
        className="inline-flex items-center gap-1 text-sm underline underline-offset-2"
      >
        <X aria-hidden="true" className="size-4" />
        {t('runs.gaia.clear')}
      </button>
    </div>
  );
}

/** Free text with examples, or a GAIA question when the backend can serve them. */
export function QuestionField({
  text,
  onTextChange,
  gaia,
  onGaiaChange,
  gaiaAvailable,
}: {
  text: string;
  onTextChange: (value: string) => void;
  gaia: GaiaQuestion | null;
  onGaiaChange: (value: GaiaQuestion | null) => void;
  gaiaAvailable: boolean;
}) {
  const { t } = useI18n();
  const [pickerOpen, setPickerOpen] = useState(false);
  const examples = [t('runs.example.1'), t('runs.example.2'), t('runs.example.3')];

  return (
    <div>
      <label htmlFor="run-question" className="mb-1 block text-sm font-medium">
        {t('runs.question')}
      </label>
      {gaia ? (
        <ChosenQuestion
          gaia={gaia}
          onClear={() => {
            onGaiaChange(null);
            onTextChange('');
          }}
        />
      ) : (
        <>
          <textarea
            id="run-question"
            rows={3}
            value={text}
            placeholder={t('runs.question.placeholder')}
            onChange={(event) => onTextChange(event.target.value)}
            className={`${FIELD} py-2`}
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="text-xs text-fg-muted">{t('runs.examples')}</span>
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => onTextChange(example)}
                className="rounded-full border border-line px-2.5 py-1 text-xs hover:bg-muted"
              >
                {example}
              </button>
            ))}
            {gaiaAvailable && (
              <button
                type="button"
                onClick={() => setPickerOpen(true)}
                className="rounded-full border border-line-strong px-2.5 py-1 text-xs font-medium hover:bg-muted"
              >
                {t('runs.gaia.pick')}
              </button>
            )}
          </div>
        </>
      )}
      <GaiaPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={(item) => {
          onGaiaChange(item);
          onTextChange(item.question);
        }}
      />
    </div>
  );
}
