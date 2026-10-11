import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Drawer, Modal } from './Modal.jsx'

function Opener({ Overlay = Modal }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button onClick={() => setOpen(true)}>open it</button>
      {open && (
        <Overlay title="Edit thing" onClose={() => setOpen(false)}>
          <input aria-label="inner field" />
        </Overlay>
      )}
    </>
  )
}

describe('Modal', () => {
  it('is an accessible dialog named by its title, with its content and footer', () => {
    render(
      <Modal title="Add node" onClose={() => {}} footer={<button>Save</button>}>
        <p>form goes here</p>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog', { name: 'Add node' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByText('form goes here')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
  })

  it('moves focus into the dialog', () => {
    render(<Modal title="Add node" onClose={() => {}}>x</Modal>)
    expect(screen.getByRole('dialog')).toHaveFocus()
  })

  it('closes on Escape, on the close button and on a click outside', async () => {
    const onClose = vi.fn()
    render(<Modal title="Add node" onClose={onClose}>x</Modal>)

    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(2)

    const backdrop = screen.getByRole('dialog').previousElementSibling
    await userEvent.click(backdrop)
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('does not close when clicking inside the dialog', async () => {
    const onClose = vi.fn()
    render(<Modal title="Add node" onClose={onClose}><p>inside</p></Modal>)
    await userEvent.click(screen.getByText('inside'))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('locks page scrolling while open and gives focus back to the opener afterwards', async () => {
    render(<Opener />)
    const opener = screen.getByRole('button', { name: 'open it' })
    await userEvent.click(opener)
    expect(document.body.style.overflow).toBe('hidden')
    expect(screen.getByRole('dialog', { name: 'Edit thing' })).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(document.body.style.overflow).toBe('')
    expect(opener).toHaveFocus()
  })
})

describe('Drawer', () => {
  it('is an accessible side panel with a close button', async () => {
    const onClose = vi.fn()
    render(
      <Drawer title="Event #101" onClose={onClose}>
        <p>details</p>
      </Drawer>,
    )
    expect(screen.getByRole('dialog', { name: 'Event #101' })).toHaveFocus()
    expect(screen.getByText('details')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Close panel' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('closes on Escape and restores focus', async () => {
    render(<Opener Overlay={Drawer} />)
    const opener = screen.getByRole('button', { name: 'open it' })
    await userEvent.click(opener)
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })
})
