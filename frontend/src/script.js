/* exported download, removeDownload */
'use strict'

const trackedIds = new window.Set()

/**
 * Adds a completeled download to the downloads table on the UI.
 *
 * @param {string} prettyName Human-readable name of the download.
 * @param {string} key Unique key that identifies this download (use for deletes).
 * @param {string} path Relative path to the download directory for this item.
 */
function createDownloadListing(prettyName, key, path) {
  const table = document.getElementById('availableFiles')
  const tbody = table.getElementsByTagName('tbody')[0]
  const newRow = tbody.insertRow(0)
  const nameCell = newRow.insertCell()
  const downloadCell = newRow.insertCell()
  const managementCell = newRow.insertCell()
  const deleteIconSpan = document.createElement('span')

  newRow.id = key
  nameCell.innerHTML = prettyName
  downloadCell.innerHTML = `<a href="${path}/">Download</a>`

  /* Need to wrap the Font Awesome icon in a span in order to have something stable to attach events to.
  FA replaces the <i> tag with a <svg> tag so attaching directly to the FA resource does not work */
  deleteIconSpan.innerHTML = '<i class="fas fa-trash"></i>'
  managementCell.appendChild(deleteIconSpan)
  deleteIconSpan.addEventListener('click', function () {
    removeDownload(key)
  })

  table.classList.remove('is-hidden')
  document.getElementById('noAvailableFiles').classList.add('is-hidden')
}

/**
 * Requests a download of a resource given the parameters in the form on the page.
 */
function download() {
  const url = document.getElementById('url')
  const downloadType = document.querySelector('input[name="download_type"]:checked').value
  const params = {}

  if (!url.value.trim()) {
    document.getElementById('urlError').classList.remove('is-hidden')
    url.classList.add('is-danger')
    return
  } else {
    document.getElementById('urlError').classList.add('is-hidden')
    url.classList.remove('is-danger')
  }

  params.url = url.value
  if (downloadType === 'both') {
    params.download_video = true
    params.extract_audio = true
  } else if (downloadType === 'video') {
    params.download_video = true
    params.extract_audio = false
  } else if (downloadType === 'audio') {
    params.download_video = false
    params.extract_audio = true
  }

  const request = new window.XMLHttpRequest()

  request.error = function () {
    console.log('This is unexpected')
  }
  request.onload = function () {
    if (this.status === 202) {
      const resp = JSON.parse(this.response)
      trackedIds.add(resp.req_id)
      document.getElementById(
        'downloads'
      ).innerHTML += `<div id="${resp.req_id}:div"><h3 class="subtitle is-6">Request ${resp.req_id} for ${params.url}</h3></div>`
      document.getElementById('noDownloads').classList.add('is-hidden')
    }
  }

  request.open('POST', '/api/download', true)
  request.setRequestHeader('Content-Type', 'application/json')
  request.send(JSON.stringify(params))
  url.value = ''
}

/**
 * Main loop of the UI.  Processes incoming websocket messages and updates the UI accordingly.
 *
 * @param {*} event The websocket event.
 */
function handleWSMessage(event) {
  const msg = JSON.parse(event.data)
  const table = document.getElementById('availableFiles')
  const tbody = table.getElementsByTagName('tbody')[0]

  if (msg.status === 'CONNECTED') {
    msg.downloads.forEach((download) => {
      createDownloadListing(download.pretty_name, download.key, download.path)
    })
  } else if (msg.status === 'DELETED') {
    document.getElementById(msg.key).remove()

    if (tbody.rows.length === 0) {
      table.classList.add('is-hidden')
      document.getElementById('noAvailableFiles').classList.remove('is-hidden')
    }
  } else if (msg.status === 'COMPLETED') {
    createDownloadListing(msg.pretty_name, msg.key, msg.path)

    if (trackedIds.has(msg.req_id)) {
      trackedIds.delete(msg.req_id)

      const reqDiv = document.getElementById(`${msg.req_id}:div`)
      if (reqDiv) {
        reqDiv.remove()
      }

      if (trackedIds.size === 0) {
        document.getElementById('noDownloads').classList.remove('is-hidden')
      }
    }
  } else if (msg.status === 'DOWNLOADING' && trackedIds.has(msg.req_id)) {
    const progressBar = document.getElementById(`${msg.req_id}:${msg.filename}:progress`)
    const reqDiv = document.getElementById(`${msg.req_id}:div`)

    if (progressBar) {
      progressBar.value = (msg.downloaded_bytes / msg.total_bytes) * 100
    } else {
      reqDiv.innerHTML += `
      <div id="${msg.req_id}:${msg.filename}:div">
        <label class="label">${msg.filename}</label>
        <progress class="progress" value="0" max="100" id="${msg.req_id}:${msg.filename}:progress">0</progress>
      </div>`
    }
  } else if (msg.status === 'DOWNLOADED' && trackedIds.has(msg.req_id)) {
    const progressBar = document.getElementById(`${msg.req_id}:${msg.filename}:progress`)
    progressBar.removeAttribute('value')
  } else if (msg.status === 'ERROR' && trackedIds.has(msg.req_id)) {
    const reqDiv = document.getElementById(`${msg.req_id}:div`)
    const progressBars = reqDiv.getElementsByTagName('progress')
    for (let i = progressBars.length - 1; i > 0; i--) {
      progressBars[i].remove()
    }
    reqDiv.innerHTML += `<p class="help is-danger">Error: ${msg.msg}</p>`
  }
}

/**
 * Sends a delete request for a given key, defers local processing until response comes back on websocket.
 *
 * @param {string} key The reference key that identifies a previous download.
 */
function removeDownload(key) {
  const request = new window.XMLHttpRequest()

  request.error = function () {
    console.log('This is unexpected')
  }

  request.open('DELETE', '/api/remove', true)
  request.setRequestHeader('Content-Type', 'application/json')
  request.send(JSON.stringify({ key: key }))
}

/**
 * Connects to the server status websocket on window load.
 */
function connectWS() {
  const wsProto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new window.WebSocket(`${wsProto}://${window.location.host}/api/status`)
  ws.onmessage = handleWSMessage
  ws.onclose = function () {
    // Clear the downloaded area
    const table = document.getElementById('availableFiles')
    document.getElementById('noAvailableFiles').classList.remove('is-hidden')
    for (let i = table.rows.length - 1; i > 0; i--) {
      table.deleteRow(i)
    }
    table.classList.add('is-hidden')

    // Clear the downloading area
    trackedIds.forEach((reqId) => {
      const reqDiv = document.getElementById(`${reqId}:div`)

      if (reqDiv) {
        reqDiv.remove()
      }
    })
    document.getElementById('noDownloads').classList.remove('is-hidden')

    // Clear all the tracked IDs
    trackedIds.clear()

    // Schedule a reconnect
    setTimeout(connectWS, 3000)
  }
}

window.addEventListener('load', connectWS)
