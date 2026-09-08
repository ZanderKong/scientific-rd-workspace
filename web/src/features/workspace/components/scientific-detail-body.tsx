'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import type { DataRecord } from '@/lib/domain';
import { enrichScientificDocument } from '../scientific-document/model';

const ReadOnlyComposer = dynamic(
  () =>
    import('../scientific-composer/scientific-composer').then(
      (module) => module.ScientificComposer
    ),
  { ssr: false }
);

export function DataDetailBody({
  record,
  compact = false
}: {
  record: DataRecord;
  compact?: boolean;
}) {
  const blocks = enrichScientificDocument(record.document, record.occurrences);
  return (
    <div className='space-y-5'>
      {blocks.length > 0 && (
        <section className='rounded-xl border bg-card/80 p-4'>
          <h2 className='mb-3 font-semibold'>获取正文</h2>
          <ReadOnlyComposer
            initialBlocks={blocks}
            searchProcesses={async () => []}
            searchObjects={async () => []}
            onChange={() => undefined}
            editable={false}
          />
        </section>
      )}
      <section className={`grid gap-3 ${compact ? '' : 'md:grid-cols-2'}`}>
        {record.representations.map((representation) => (
          <article key={representation.id} className='rounded-xl border bg-card/80 p-4'>
            <div className='flex items-center justify-between gap-2'>
              <h2 className='font-semibold'>{representation.name}</h2>
              <span className='rounded-full bg-muted px-2 py-1 text-xs'>{representation.kind}</span>
            </div>
            {representation.scalar && (
              <p className='mt-3 text-lg font-medium'>
                {representation.scalar.value} {representation.scalar.unit ?? ''}
              </p>
            )}
            {!!representation.table_rows_count && (
              <p className='mt-2 text-sm text-muted-foreground'>
                {representation.table_rows_count} rows
              </p>
            )}
            {representation.inline_payload_jsonb && (
              <dl className='mt-3 grid gap-1 text-xs'>
                {Object.entries(representation.inline_payload_jsonb)
                  .slice(0, compact ? 3 : 8)
                  .map(([key, value]) => (
                    <div key={key} className='flex justify-between gap-3'>
                      <dt className='text-muted-foreground'>{key}</dt>
                      <dd className='truncate'>{String(value)}</dd>
                    </div>
                  ))}
              </dl>
            )}
            {representation.asset_id && (
              <Link
                className='mt-3 inline-block text-sm text-primary hover:underline'
                href={api.downloadUrl(representation.asset_id)}
              >
                下载附件
              </Link>
            )}
            <p className='mt-3 font-mono text-[10px] text-muted-foreground'>
              {representation.representation_sha256.slice(0, 16)}…
            </p>
          </article>
        ))}
        {!record.representations.length && (
          <p className='rounded-xl border border-dashed p-6 text-sm text-muted-foreground'>
            此版本没有 Representation。
          </p>
        )}
      </section>
    </div>
  );
}
