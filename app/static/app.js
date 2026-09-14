// FreezerBags client behaviour: dialogs + the portion stepper.
// Everything is delegated on document so it keeps working after htmx swaps
// #item-list back in with fresh markup.

document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-open-dialog]");
  if (opener) {
    const dialog = document.getElementById(opener.dataset.openDialog);
    if (dialog) {
      resetPicker(dialog);
      dialog.showModal();
    }
    return;
  }

  const closer = event.target.closest("[data-close-dialog]");
  if (closer) {
    const dialog = document.getElementById(closer.dataset.closeDialog);
    if (dialog) dialog.close();
    return;
  }

  // Click on the dialog backdrop (the <dialog> element itself, not its content) closes it.
  if (event.target.tagName === "DIALOG") {
    event.target.close();
    return;
  }

  const step = event.target.closest(".portion-step");
  if (step) {
    setPortion(step.closest("[data-portion-picker]"), Number(step.dataset.set));
    return;
  }

  const adjust = event.target.closest(".portion-adjust");
  if (adjust) {
    const picker = adjust.closest("[data-portion-picker]");
    const current = Number(picker.querySelector("input[type=hidden]").value) || 1;
    setPortion(picker, current + Number(adjust.dataset.adjust));
  }
});

function setPortion(picker, value) {
  if (!picker) return;
  const max = Number(picker.dataset.max) || 99;
  const clamped = Math.min(Math.max(value, 1), max);
  picker.querySelector("input[type=hidden]").value = clamped;
  picker.querySelector(".portion-value").textContent = clamped;
}

function resetPicker(scope) {
  const picker = scope.querySelector("[data-portion-picker]");
  if (picker) setPortion(picker, 1);
}

// Clear the add-food form once it's been successfully submitted via htmx.
document.body.addEventListener("htmx:afterRequest", (event) => {
  const form = event.target.closest("form[data-reset-on-success]");
  if (form && event.detail.successful) {
    form.reset();
    resetPicker(form);
  }
});
