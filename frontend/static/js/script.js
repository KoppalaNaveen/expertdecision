console.log("Expert Decision Replay Platform");

function showToast(titleOrMessage, message=null) {
    let type = "success";
    let body = titleOrMessage;
    let title = null;

    if (message !== null) {
        const t = String(titleOrMessage).toLowerCase();
        if (t === "danger" || t === "error") {
            type = "danger";
            title = titleOrMessage;
        } else if (t === "warning") {
            type = "warning";
        } else if (t === "info") {
            type = "info";
        } else {
            type = "success";
        }
        body = message;
    } else {
        if (typeof titleOrMessage === "string" && (titleOrMessage.toLowerCase().includes("error") || titleOrMessage.toLowerCase().includes("failed") || titleOrMessage.toLowerCase().includes("invalid"))) {
            type = "danger";
        }
    }

    if (type === "danger" || type === "error") {
        if (typeof showGlobalErrorNotification === 'function') {
            showGlobalErrorNotification(body, 6000, title || "Error");
            return;
        }
    }

    const toastEl = document.getElementById("liveToast");
    if (!toastEl) return;
    const toastBody = document.getElementById("toastMessage");
    toastBody.innerText = body;
    
    // reset classes
    toastEl.classList.remove("text-bg-success", "text-bg-danger", "text-bg-warning", "text-bg-info");
    toastEl.classList.add("text-bg-" + type);

    const toast = new bootstrap.Toast(toastEl);
    toast.show();
}