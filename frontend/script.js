const trackedIds = new Set();

/**
 * Adds a completeled download to the downloads table on the UI.
 *
 * @param {string} pretty_name Human-readable name of the download.
 * @param {string} key Unique key that identifies this download (use for deletes).
 * @param {string} path Relative path to the download directory for this item.
 */
function createDownloadListing(pretty_name, key, path) {
  const table = document.getElementById("availableFiles"),
    tbody = table.getElementsByTagName("tbody")[0],
    newRow = tbody.insertRow(0),
    nameCell = newRow.insertCell(),
    downloadCell = newRow.insertCell(),
    managementCell = newRow.insertCell();

  newRow.id = key;
  nameCell.innerHTML = pretty_name;
  downloadCell.innerHTML = `<a href="${path}">Download</a>`;
  managementCell.innerHTML = `<i class="fas fa-trash" style="color: red" onclick="removeDownload('${key}')"></i>`;
  table.classList.remove("is-hidden");
  document.getElementById("noAvailableFiles").classList.add("is-hidden");
}

/**
 * Requests a download of a resource given the parameters in the form on the page.
 */
function download() {
  const url = document.getElementById("url"),
    downloadType = document.querySelector('input[name="download_type"]:checked')
      .value,
    params = {};

  if (!url.value.trim()) {
    document.getElementById("urlError").classList.remove("is-hidden");
    url.classList.add("is-danger");
    return;
  } else {
    document.getElementById("urlError").classList.add("is-hidden");
    url.classList.remove("is-danger");
  }

  params.url = url.value;
  if (downloadType === "both") {
    params.download_video = true;
    params.extract_audio = true;
  } else if (downloadType === "video") {
    params.download_video = true;
    params.extract_audio = false;
  } else if (downloadType === "audio") {
    params.download_video = false;
    params.extract_audio = true;
  }

  const request = new XMLHttpRequest();

  request.error = function () {
    console.log("This is unexpected");
  };
  request.onload = function () {
    if (this.status === 202) {
      const resp = JSON.parse(this.response);
      trackedIds.add(resp["req_id"]);
    }
  };

  request.open("POST", "/api/download", true);
  request.setRequestHeader("Content-Type", "application/json");
  request.send(JSON.stringify(params));
  url.value = "";
}

/**
 * Main loop of the UI.  Processes incoming websocket messages and updates the UI accordingly.
 *
 * @param {*} event The websocket event.
 */
function handleWSMessage(event) {
  const msg = JSON.parse(event.data),
    table = document.getElementById("availableFiles"),
    tbody = table.getElementsByTagName("tbody")[0];
  if (msg.downloads) {
    msg.downloads.forEach((download) => {
      createDownloadListing(download.pretty_name, download.key, download.path);
    });
  } else if (msg.status === "DELETED") {
    document.getElementById(msg.key).remove();

    if (tbody.rows.length === 0) {
      table.classList.add("is-hidden");
      document.getElementById("noAvailableFiles").classList.remove("is-hidden");
    }
  } else if (msg.status === "COMPLETED") {
    createDownloadListing(msg.pretty_name, msg.key, msg.path);
    trackedIds.delete(msg["req_id"]);

    if (trackedIds.size === 0) {
      document.getElementById("noDownloads").classList.remove("is-hidden");
    }
  } else if (msg.status === "DOWNLOADING" && trackedIds.has(msg.req_id)) {
    const progress_bar = document.getElementById(
      `${msg.req_id}:${msg.filename}:progress`
    );
    let req_div = document.getElementById(`${msg.req_id}:div`);
    document.getElementById("noDownloads").classList.add("is-hidden");

    if (!req_div) {
      document.getElementById(
        "downloads"
      ).innerHTML += `<div id="${msg.req_id}:div"></div>`;
      req_div = document.getElementById(`${msg.req_id}:div`);
    }

    if (progress_bar) {
      progress_bar.value = (msg.downloaded_bytes / msg.total_bytes) * 100;
    } else {
      req_div.innerHTML += `
        <label class="label">${msg.filename}</label>
        <progress class="progress" value="0" max="100" id="${msg.req_id}:${msg.filename}:progress">0</progress>`;
    }
  } else if (msg.status === "DOWNLOADED" && trackedIds.has(msg.req_id)) {
    const req_div = document.getElementById(`${msg.req_id}:div`);
    if (req_div) {
      req_div.remove();
    }
  }
}

/**
 * Sends a delete request for a given key, defers local processing until response comes back on websocket.
 *
 * @param {string} key The reference key that identifies a previous download.
 */
function removeDownload(key) {
  const request = new XMLHttpRequest();

  request.error = function () {
    console.log("This is unexpected");
  };

  request.open("DELETE", "/api/remove", true);
  request.setRequestHeader("Content-Type", "application/json");
  request.send(JSON.stringify({ key: key }));
}

/**
 * Connects to the server status websocket on window load.
 */
function connectWS() {
  const ws_proto = window.location.protocol === "https:" ? "wss" : "ws",
    ws = new WebSocket(`${ws_proto}://${window.location.host}/api/status`);
  ws.onmessage = handleWSMessage;
}

window.addEventListener("load", connectWS);
