import { useState, type FormEvent } from 'react'
import { photoUrl, useAction, type Model } from '../api'
import { useI18n } from '../i18n'
import { Alert, Empty, Panel } from './ui'

export function Upload({ kind, owner, multiple = true }: { kind: 'user' | 'match' | 'tournament', owner: string, multiple?: boolean }) {
  const { t } = useI18n()
  const mutation = useAction()
  const [selected, setSelected] = useState<File[]>([])
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const body = new FormData()
    for (const file of selected) body.append('files', file)
    mutation.mutate({ path: `/media/${kind}/${owner}`, body }, {
      onSuccess: () => { form.reset(); setSelected([]) },
    })
  }
  return <form className="upload-form" onSubmit={submit}>
    <label>{t('chooseFiles')}<input type="file" accept="image/png,image/jpeg,image/webp" multiple={multiple}
      onChange={event => setSelected(Array.from(event.target.files ?? []))} required /></label>
    <button disabled={mutation.isPending || !selected.length}>{t(mutation.isPending ? 'saving' : 'upload')}</button>
    <Alert error={mutation.error} />
    {mutation.isSuccess && <p role="status">{t('saved')}</p>}
  </form>
}

export function Gallery({ photos, admin, tournamentId }: { photos: Model['Photo'][], admin?: boolean, tournamentId?: string }) {
  const { t } = useI18n()
  const mutation = useAction()
  const [remove, setRemove] = useState<string | null>(null)
  return <Panel title={t('gallery')}>
    {!photos.length && <Empty />}
    <ul className="gallery">
      {photos.map(photo => <li key={photo.id}>
        <a href={photoUrl(photo.id, 'full')} aria-label={t('viewPhoto')} target="_blank" rel="noreferrer">
          <img alt="" src={photoUrl(photo.id)} loading="lazy" crossOrigin="anonymous" />
        </a>
        {admin && <div className="photo-controls">
          {tournamentId && <button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({
            path: `/tournaments/${tournamentId}/cover`, method: 'PUT', body: { photo_id: photo.cover ? null : photo.id },
          })}>{t(photo.cover ? 'clearCover' : 'setCover')}</button>}
          {remove === photo.id
            ? <><button className="danger" type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({
              path: `/admin/media/${photo.id}`, method: 'DELETE',
            }, { onSuccess: () => setRemove(null) })}>{t('confirm')}</button>
            <button type="button" onClick={() => setRemove(null)}>{t('cancel')}</button></>
            : <button type="button" onClick={() => setRemove(photo.id)}>{t('delete')}</button>}
        </div>}
      </li>)}
    </ul>
    <Alert error={mutation.error} />
  </Panel>
}
