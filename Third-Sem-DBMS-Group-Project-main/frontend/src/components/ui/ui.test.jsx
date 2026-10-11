import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Button, IconButton } from './Button.jsx'
import { Card, CardBody, CardHeader } from './Card.jsx'
import { Field, SearchInput, Select, TextInput } from './Fields.jsx'
import { DestinationName, DetailList, KpiCard, PageHeader, RangeSelect } from './Misc.jsx'
import { Pagination } from './Pagination.jsx'
import { Badge, StatusBadge } from './StatusBadge.jsx'
import { Table, TableWrap, Td, Th, Tr } from './Table.jsx'

const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>)

describe('StatusBadge', () => {
  it.each([
    ['ACTIVE', 'Active', 'text-ok'],
    ['OFFLINE', 'Offline', 'text-muted'],
    ['INACTIVE', 'Inactive', 'text-muted'],
    ['UNKNOWN', 'Unknown', 'text-warn'],
    ['DISABLED', 'Disabled', 'text-muted'],
    ['ADMIN', 'Admin', 'text-accent'],
    ['ANALYST', 'Analyst', 'text-ink/80'],
  ])('%s is shown as "%s" with the right tone', (status, label, toneClass) => {
    render(<StatusBadge status={status} />)
    expect(screen.getByText(label).closest('span')).toHaveClass(toneClass)
  })

  it('shows an unknown value as-is instead of failing', () => {
    render(<StatusBadge status="SOMETHING_NEW" />)
    expect(screen.getByText('SOMETHING_NEW')).toBeInTheDocument()
  })

  it('Badge renders its children', () => {
    render(<Badge tone="danger">Boom</Badge>)
    expect(screen.getByText('Boom')).toHaveClass('text-danger')
  })
})

describe('Button', () => {
  it('calls onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Save</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled and inert while loading', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Saving
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Saving' })
    expect(button).toBeDisabled()
    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('does not submit forms unless asked to (type defaults to button)', () => {
    render(<Button>Plain</Button>)
    expect(screen.getByRole('button', { name: 'Plain' })).toHaveAttribute('type', 'button')
  })

  it('IconButton is named by its label', async () => {
    const onClick = vi.fn()
    render(<IconButton icon={() => <svg />} label="Close panel" onClick={onClick} />)
    await userEvent.click(screen.getByRole('button', { name: 'Close panel' }))
    expect(onClick).toHaveBeenCalled()
  })
})

describe('Card', () => {
  it('renders header, body and actions', () => {
    render(
      <Card>
        <CardHeader title="Top destinations" subtitle="last 24 hours" actions={<button>All</button>} />
        <CardBody>content</CardBody>
      </Card>,
    )
    expect(screen.getByRole('heading', { name: 'Top destinations' })).toBeInTheDocument()
    expect(screen.getByText('last 24 hours')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByText('content')).toBeInTheDocument()
  })
})

describe('form fields', () => {
  it('Field ties its label to the control', async () => {
    render(<Field label="Node code">{(id) => <TextInput id={id} />}</Field>)
    await userEvent.type(screen.getByLabelText('Node code'), 'LAB-A')
    expect(screen.getByLabelText('Node code')).toHaveValue('LAB-A')
  })

  it('Field shows an error as an alert (instead of the hint)', () => {
    render(
      <Field label="Name" error="Name is required" hint="A hint">
        {(id) => <TextInput id={id} />}
      </Field>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Name is required')
    expect(screen.queryByText('A hint')).not.toBeInTheDocument()
  })

  it('Field shows the hint when there is no error', () => {
    render(
      <Field label="Name" hint="A hint">
        {(id) => <TextInput id={id} />}
      </Field>,
    )
    expect(screen.getByText('A hint')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('controls fill their container unless a width is given', () => {
    render(
      <>
        <TextInput aria-label="wide" />
        <Select aria-label="narrow" className="w-40" />
      </>,
    )
    expect(screen.getByLabelText('wide')).toHaveClass('w-full')
    expect(screen.getByLabelText('narrow')).toHaveClass('w-40')
    expect(screen.getByLabelText('narrow')).not.toHaveClass('w-full')
  })

  it('SearchInput reports what is typed', async () => {
    const onChange = vi.fn()
    render(<SearchInput value="" onChange={onChange} label="Search nodes" />)
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search nodes' }), 'ab')
    expect(onChange).toHaveBeenNthCalledWith(1, 'a')
    expect(onChange).toHaveBeenNthCalledWith(2, 'b')
  })

  it('Select lets the user choose', async () => {
    const onChange = vi.fn()
    render(
      <Select aria-label="Status" defaultValue="" onChange={onChange}>
        <option value="">All</option>
        <option value="ACTIVE">Active</option>
      </Select>,
    )
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'ACTIVE')
    expect(onChange).toHaveBeenCalled()
    expect(screen.getByLabelText('Status')).toHaveValue('ACTIVE')
  })
})

describe('Pagination', () => {
  it('shows the range and page, and moves forward', async () => {
    const onPageChange = vi.fn()
    render(<Pagination data={{ total: 60, page: 1, page_size: 25 }} onPageChange={onPageChange} />)
    expect(screen.getByText('1–25 of 60')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('moves back from a middle page and cannot go past the last page', async () => {
    const onPageChange = vi.fn()
    const { rerender } = render(<Pagination data={{ total: 60, page: 2, page_size: 25 }} onPageChange={onPageChange} />)
    expect(screen.getByText('26–50 of 60')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Previous page' }))
    expect(onPageChange).toHaveBeenCalledWith(1)

    rerender(<Pagination data={{ total: 60, page: 3, page_size: 25 }} onPageChange={onPageChange} />)
    expect(screen.getByText('51–60 of 60')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  })

  it('handles an empty result', () => {
    render(<Pagination data={{ total: 0, page: 1, page_size: 25 }} onPageChange={() => {}} />)
    expect(screen.getByText('No results')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  })

  it('formats large numbers', () => {
    render(<Pagination data={{ total: 12345, page: 1, page_size: 25 }} onPageChange={() => {}} />)
    expect(screen.getByText('1–25 of 12,345')).toBeInTheDocument()
  })
})

describe('Table', () => {
  it('makes a clickable row keyboard-accessible', async () => {
    const onClick = vi.fn()
    render(
      <TableWrap>
        <Table>
          <thead>
            <tr>
              <Th>Name</Th>
              <Th align="right">Count</Th>
            </tr>
          </thead>
          <tbody>
            <Tr onClick={onClick}>
              <Td>alpha</Td>
              <Td align="right">3</Td>
            </Tr>
          </tbody>
        </Table>
      </TableWrap>,
    )
    const row = screen.getByRole('row', { name: /alpha/ })
    expect(row).toHaveAttribute('tabindex', '0')
    await userEvent.click(row)
    expect(onClick).toHaveBeenCalledTimes(1)

    row.focus()
    await userEvent.keyboard('{Enter}')
    await userEvent.keyboard(' ')
    expect(onClick).toHaveBeenCalledTimes(3)
    expect(screen.getByRole('columnheader', { name: 'Count' })).toHaveClass('text-right')
  })

  it('leaves a plain row out of the tab order', () => {
    render(
      <Table>
        <tbody>
          <Tr>
            <Td>plain</Td>
          </Tr>
        </tbody>
      </Table>,
    )
    expect(screen.getByRole('row')).not.toHaveAttribute('tabindex')
  })
})

describe('KpiCard', () => {
  it('shows label, value and hint', () => {
    render(<KpiCard label="Active nodes" value="4" hint="of 4 registered" />)
    expect(screen.getByText('Active nodes')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('of 4 registered')).toBeInTheDocument()
  })

  it('hides the value and hint behind a skeleton while loading', () => {
    render(<KpiCard label="Active nodes" value="4" hint="of 4 registered" loading />)
    expect(screen.queryByText('4')).not.toBeInTheDocument()
    expect(screen.queryByText('of 4 registered')).not.toBeInTheDocument()
  })

  it('becomes a link when given a destination', () => {
    inRouter(<KpiCard label="Nodes" value="4" to="/nodes" />)
    expect(screen.getByRole('link')).toHaveAttribute('href', '/nodes')
  })
})

describe('DetailList', () => {
  it('lists labels and values, using a dash for missing values', () => {
    render(
      <DetailList
        items={[
          { label: 'Name', value: 'Computer Lab A' },
          { label: 'Description', value: null },
          { label: 'IP', value: '10.10.1.1', mono: true },
        ]}
      />,
    )
    expect(screen.getByText('Computer Lab A')).toBeInTheDocument()
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText('10.10.1.1')).toHaveClass('font-mono')
  })
})

describe('PageHeader', () => {
  it('renders title, subtitle, breadcrumb and actions, and names the browser tab', () => {
    render(<PageHeader title="Nodes" subtitle="Observation points" breadcrumb={<a href="/x">Back</a>} actions={<button>Add</button>} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Nodes' })).toBeInTheDocument()
    expect(screen.getByText('Observation points')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument()
    expect(document.title).toBe('Nodes · NetMonitor')
  })
})

describe('RangeSelect', () => {
  it('marks the current range and reports a change', async () => {
    const onChange = vi.fn()
    render(<RangeSelect value="7d" onChange={onChange} />)
    const group = screen.getByRole('group', { name: 'Time range' })
    expect(within(group).getByRole('button', { name: '7 days' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(group).getByRole('button', { name: '24 hours' })).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(within(group).getByRole('button', { name: '30 days' }))
    expect(onChange).toHaveBeenCalledWith('30d')
  })

  it('accepts custom options', () => {
    render(<RangeSelect value="a" onChange={() => {}} options={[{ value: 'a', label: 'Alpha' }, { value: 'custom', label: 'Custom range' }]} />)
    expect(screen.getByRole('button', { name: 'Custom range' })).toBeInTheDocument()
  })
})

describe('DestinationName', () => {
  it('shows the domain when there is one', () => {
    render(<DestinationName domain="github.com" ip="203.0.113.20" />)
    expect(screen.getByText('github.com')).toBeInTheDocument()
    expect(screen.queryByText(/unresolved/)).not.toBeInTheDocument()
  })
  it('shows the IP and marks it unresolved (never invents a name)', () => {
    render(<DestinationName domain={null} ip="192.0.2.77" />)
    expect(screen.getByText(/192\.0\.2\.77/)).toBeInTheDocument()
    expect(screen.getByText('(unresolved)')).toBeInTheDocument()
  })
})
